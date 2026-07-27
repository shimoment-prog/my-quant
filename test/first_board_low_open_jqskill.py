# -*- coding: utf-8 -*-
"""
首板低开策略（joinquant-skill 生成）

股票池：过滤 ST / 科创板 / 北交所 / 上市未满一年次新股 / 停牌
选股（同时满足）：
  1) 昨日涨停且为首板（前日未涨停）
  2) 昨收处于近 60 日高低中位线以下
  3) 今日低开幅度 ∈ [-4%, -3%]（闭区间默认）
买入：符合条件全部等权（按可用现金）
卖出：次日上午盈利则卖；否则尾盘无条件清仓

回测建议：分钟频率，便于上午盈亏判断更贴近实盘。
"""

from jqdata import *


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ), type='stock')
    set_slippage(PriceRelatedSlippage(0.00246))

    # 记录买入日期，避免误卖当日新开仓
    g.buy_dates = {}

    # 先卖后买；尾盘清掉未盈利隔夜仓
    run_daily(morning_sell, time='09:31')
    run_daily(buy_stocks, time='09:32')
    run_daily(close_sell, time='14:50')  # 尾盘清仓（平台不支持 before_close）


def is_limit_up(close_price, high_limit):
    """涨停判断，留浮点误差"""
    if high_limit is None or high_limit != high_limit or high_limit <= 0:
        return False
    return close_price >= high_limit * 0.997


def filter_stock_pool(context, stock_list):
    """过滤 ST、科创板、北交所、次新、停牌、退市整理"""
    current_data = get_current_data()
    today = context.current_dt.date()
    result = []

    for stock in stock_list:
        if stock.startswith('688'):
            continue
        if stock.endswith('.XBEI'):
            continue

        info = get_security_info(stock)
        if (today - info.start_date).days < 365:
            continue

        cd = current_data[stock]
        if cd.paused or cd.is_st:
            continue
        if 'ST' in cd.name or '*' in cd.name or '退' in cd.name:
            continue

        result.append(stock)

    return result


def check_signal(context, stock):
    """三条件同时满足才入选"""
    current_data = get_current_data()
    cd = current_data[stock]
    if cd.paused:
        return False

    # attribute_history 天级不含当天，自动防未来函数
    hist = attribute_history(
        stock, 60, '1d',
        ['high', 'low', 'close', 'high_limit'],
        skip_paused=True, df=True,
    )
    if hist is None or len(hist) < 60:
        return False

    y_close = hist['close'][-1]
    y_high_limit = hist['high_limit'][-1]
    dby_close = hist['close'][-2]
    dby_high_limit = hist['high_limit'][-2]

    # 条件一：昨日涨停且首板
    if not is_limit_up(y_close, y_high_limit):
        return False
    if is_limit_up(dby_close, dby_high_limit):
        return False

    # 条件二：相对低位（用昨收 vs 60 日高低中位）
    mid_price = (hist['high'].max() + hist['low'].min()) / 2.0
    if y_close >= mid_price:
        return False

    # 条件三：今日低开 -4% ~ -3%
    day_open = cd.day_open
    if day_open is None or day_open != day_open or day_open <= 0 or y_close <= 0:
        return False
    open_pct = day_open / y_close - 1.0
    if open_pct < -0.04 or open_pct > -0.03:
        return False

    # 开盘跌停买不进
    if day_open <= cd.low_limit * 1.003:
        return False

    return True


def morning_sell(context):
    """次日上午：现价高于成本则卖出"""
    current_data = get_current_data()
    today = context.current_dt.date()

    for stock in list(context.portfolio.positions.keys()):
        buy_date = g.buy_dates.get(stock)
        if buy_date is None or buy_date >= today:
            continue

        pos = context.portfolio.positions[stock]
        if pos.total_amount <= 0:
            continue

        last_price = current_data[stock].last_price
        if last_price > pos.avg_cost:
            order_target(stock, 0)
            g.buy_dates.pop(stock, None)
            log.info('上午盈利卖出 %s 成本=%.2f 现价=%.2f' % (
                stock, pos.avg_cost, last_price))


def buy_stocks(context):
    """开盘选股：符合条件全部等权买入"""
    all_stocks = list(get_all_securities(['stock'], context.current_dt.date()).index)
    pool = filter_stock_pool(context, all_stocks)

    # 只读 keys，勿对未持仓代码做 positions[code]/get，否则会刷空 Position 警告
    held = set(context.portfolio.positions.keys())

    candidates = []
    for stock in pool:
        if stock in held:
            continue
        try:
            if check_signal(context, stock):
                candidates.append(stock)
        except Exception:
            continue

    if not candidates:
        log.info('今日无符合条件标的')
        return

    cash = context.portfolio.available_cash
    if cash <= 0:
        log.info('可用现金不足，跳过买入')
        return

    value_per = cash / len(candidates)
    today = context.current_dt.date()
    for stock in candidates:
        order_value(stock, value_per)
        g.buy_dates[stock] = today
        log.info('买入 %s 目标金额=%.2f' % (stock, value_per))


def close_sell(context):
    """尾盘：昨日买入且仍持有的，无论盈亏清仓"""
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
        log.info('尾盘清仓 %s 成本=%.2f 现价=%.2f' % (
            stock, pos.avg_cost, pos.price))
