# 首板低开策略（聚宽）
# 选股：昨日首板涨停 + 60日相对低位 + 今日低开 -4%~-3%
# 买入：符合条件全部等权买入
# 卖出：次日上午盈利则卖；否则拿到尾盘无条件卖出


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('order', 'error')

    # 佣金：买入万三、卖出万三+印花税千一，最低5元
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        ),
        type='stock',
    )

    # 记录持仓买入日期，便于判断“次日”卖出
    g.buy_dates = {}

    # 上午先处理昨日持仓卖出，再选股买入；尾盘清掉未盈利持仓
    run_daily(morning_sell, time='09:31')
    run_daily(buy_stocks, time='09:32')
    run_daily(close_sell, time='14:50')


def is_limit_up(close_price, high_limit):
    """判断是否涨停（留一点浮点误差）"""
    if high_limit is None or high_limit != high_limit or high_limit <= 0:
        return False
    return close_price >= high_limit * 0.997


def filter_stock_pool(context, stock_list):
    """过滤 ST、科创板、北交所、上市未满一年、停牌、退市整理"""
    current_data = get_current_data()
    today = context.current_dt.date()
    result = []

    for stock in stock_list:
        # 科创板
        if stock.startswith('688'):
            continue
        # 北交所
        if stock.endswith('.XBEI'):
            continue

        info = get_security_info(stock)
        # 上市未满一年（次新股）
        if (today - info.start_date).days < 365:
            continue

        cd = current_data[stock]
        # ST / 停牌 / 退市整理
        if cd.is_st or cd.paused:
            continue
        if 'ST' in cd.name or '退' in cd.name:
            continue

        result.append(stock)

    return result


def check_signal(context, stock):
    """
    同时满足：
    1) 昨日涨停且为首板（前日未涨停）
    2) 昨日收盘价处于近60日高低点中位线以下
    3) 今日低开幅度在 [-4%, -3%]
    """
    current_data = get_current_data()
    cd = current_data[stock]
    if cd.paused:
        return False

    # 取近60个交易日，不含当日（attribute_history 默认不含当天）
    hist = attribute_history(
        stock,
        60,
        '1d',
        ['open', 'high', 'low', 'close', 'high_limit', 'volume'],
        skip_paused=True,
        df=True,
    )
    if hist is None or len(hist) < 60:
        return False

    y_close = hist['close'][-1]
    y_high_limit = hist['high_limit'][-1]
    dby_close = hist['close'][-2]
    dby_high_limit = hist['high_limit'][-2]

    # 条件一：昨日涨停，且是首板
    if not is_limit_up(y_close, y_high_limit):
        return False
    if is_limit_up(dby_close, dby_high_limit):
        return False

    # 条件二：相对低位 —— 当前参考价（昨日收盘） < (60日最高 + 60日最低) / 2
    high_60 = hist['high'].max()
    low_60 = hist['low'].min()
    mid_price = (high_60 + low_60) / 2.0
    if y_close >= mid_price:
        return False

    # 条件三：次日（今日）低开 -4% ~ -3%
    day_open = cd.day_open
    if day_open is None or day_open != day_open or day_open <= 0 or y_close <= 0:
        return False
    open_pct = day_open / y_close - 1.0
    if open_pct < -0.04 or open_pct > -0.03:
        return False

    # 开盘即跌停则买不进，直接跳过
    if day_open <= cd.low_limit * 1.003:
        return False

    return True


def morning_sell(context):
    """次日上午：相对成本价已盈利则卖出"""
    current_data = get_current_data()
    today = context.current_dt.date()

    for stock in list(context.portfolio.positions.keys()):
        buy_date = g.buy_dates.get(stock)
        # 只处理“昨日及更早买入”的仓位，当天新买的不卖
        if buy_date is None or buy_date >= today:
            continue

        pos = context.portfolio.positions[stock]
        if pos.total_amount <= 0:
            continue

        last_price = current_data[stock].last_price
        # 赚钱就卖（现价高于成本）
        if last_price > pos.avg_cost:
            order_target(stock, 0)
            g.buy_dates.pop(stock, None)
            log.info('上午盈利卖出: %s, 成本=%.2f, 现价=%.2f' % (stock, pos.avg_cost, last_price))


def buy_stocks(context):
    """开盘选股：符合条件全部等权买入"""
    all_stocks = list(get_all_securities(['stock'], context.current_dt.date()).index)
    pool = filter_stock_pool(context, all_stocks)

    candidates = []
    for stock in pool:
        # 已持仓的不重复买
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            continue
        try:
            if check_signal(context, stock):
                candidates.append(stock)
        except Exception:
            continue

    if not candidates:
        log.info('今日无符合条件标的')
        return

    # 用可用现金等权买入
    cash = context.portfolio.available_cash
    if cash <= 0:
        log.info('可用现金不足，跳过买入')
        return

    value_per_stock = cash / len(candidates)
    today = context.current_dt.date()

    for stock in candidates:
        order_value(stock, value_per_stock)
        g.buy_dates[stock] = today
        log.info('买入: %s, 目标金额=%.2f' % (stock, value_per_stock))


def close_sell(context):
    """尾盘：前一日买入且尚未卖出的，无论盈亏一律清仓"""
    today = context.current_dt.date()

    for stock in list(context.portfolio.positions.keys()):
        buy_date = g.buy_dates.get(stock)
        if buy_date is None or buy_date >= today:
            continue

        pos = context.portfolio.positions[stock]
        if pos.total_amount <= 0:
            continue

        order_target(stock, 0)
        g.buy_dates.pop(stock, None)
        log.info('尾盘清仓: %s, 成本=%.2f, 现价=%.2f' % (stock, pos.avg_cost, pos.price))
