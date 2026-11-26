# -*- coding: utf-8 -*-
"""聚宽：沪深300内小市值 + 高ROE双因子排名，选20只、每15交易日调仓。
依据《【量化课堂】多因子策略入门》和本项目历史克隆版本整理。
使用上一交易日可见的基本面，保留63交易日无停牌和缺失值均值填充。
分钟回测：09:31选股、09:32先卖、09:35买入、14:50重试；无额外择时止损。
本代码尚未在聚宽运行，不能据此声称复现原文42倍收益。
"""

from jqdata import *
import builtins as py_builtins
import datetime as dt
import math
import pandas as pd


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(PriceRelatedSlippage(0.00246))
    # 保留聚宽拒单、数量调整等信息，不能把未成交原因静默隐藏。
    log.set_level('order', 'info')

    # 最早的本地克隆：15交易日、63日样本、20只；不声称对应42倍截图。
    g.index = '000300.XSHG'
    g.rebalance_days = 15
    g.no_pause_days = 63
    g.hold_num = 20
    g.cash_buffer = 0.02
    g.session_count = 0
    g.last_prepare_date = None
    g.plan_date = None
    g.target_codes = []
    g.target_value = 0.0
    g.has_plan = False
    g.last_buy_callback_date = None
    g.buy_submit_count = 0
    set_costs(context)

    if context.run_params.frequency != 'minute':
        raise ValueError('本策略请在聚宽选择“分钟”回测，买卖按指定时点依次执行。')

    run_daily(prepare_plan, time='09:31')
    run_daily(execute_reductions, time='09:32')
    run_daily(execute_buys, time='09:35')
    run_daily(retry_plan, time='14:50')
    run_daily(report_execution, time='15:10')
    runtime_any = globals().get('any', py_builtins.any)
    log.info('策略版本2026-11-04-builtin-fix；频率=%s；环境any来源=%s；'
             '09:31选股/09:32减仓/09:35买入/14:50重试。' % (
                 context.run_params.frequency,
                 getattr(runtime_any, '__module__', 'unknown')))


def set_costs(context):
    """回测费用假设；早期印花税沿革未逐段还原，详见说明文档。"""
    today = context.current_dt.date()
    commission = 0.0003
    if today < dt.date(2009, 1, 1):
        commission = 0.003
    elif today < dt.date(2011, 1, 1):
        commission = 0.002
    elif today < dt.date(2013, 1, 1):
        commission = 0.001
    sell_tax = 0.0005 if today >= dt.date(2023, 8, 28) else 0.001
    set_order_cost(OrderCost(
        open_tax=0, close_tax=sell_tax,
        open_commission=commission, close_commission=commission,
        close_today_commission=0, min_commission=5,
    ), type='stock')


def valid_price(value):
    return value is not None and math.isfinite(float(value)) and value > 0


def held_positions(context):
    # 本地官方文档说明total_amount不含卖单冻结数量，不能漏算locked_amount。
    return {
        code: position for code, position in context.portfolio.positions.items()
        if position.total_amount + position.locked_amount > 0
    }


def position_value(position, price):
    return (position.total_amount + position.locked_amount) * price


def min_buy_shares(code):
    return 200 if code.startswith('688') else 100


def at_price_limit(quote):
    price = quote.last_price
    return (
        (valid_price(quote.high_limit) and price >= quote.high_limit - 0.0001)
        or (valid_price(quote.low_limit) and price <= quote.low_limit + 0.0001)
    )


def submit_target(code, target, quote, is_buy):
    if code.startswith('688'):
        # 科创板市价单须指定保护价；买单上限、卖单下限均不得越过该价格。
        protection = quote.high_limit if is_buy else quote.low_limit
        if not valid_price(protection):
            return None
        return order_target_value(code, target, style=MarketOrderStyle(protection))
    return order_target_value(code, target)


def filter_stock_pool(context, codes, current):
    """原规则只筛停牌，不额外加入ST、ROE>0或市值硬阈值。"""
    result = []
    for code in codes:
        if current[code].paused:
            continue
        history_frame = attribute_history(
            code, g.no_pause_days, '1d', ['paused'],
            skip_paused=False, df=True,
        )
        if history_frame is None or len(history_frame) < g.no_pause_days:
            continue
        # 拒绝缺失样本；日线不含当天，最后一根必须对应上一交易日。
        if history_frame.index[-1].date() != context.previous_date:
            continue
        paused = history_frame['paused']
        if paused.notna().all() and paused.eq(0).all():
            result.append(code)
    return result


def rank_factors(frame):
    """市值升序名次 + ROE降序名次，越小越好；并列均排名，再按代码破同分。"""
    if frame is None or frame.empty:
        return pd.DataFrame()
    result = frame[['code', 'market_cap', 'roe']].copy()
    result = result.dropna(subset=['code']).drop_duplicates('code')
    for column in ['market_cap', 'roe']:
        values = pd.to_numeric(result[column], errors='coerce')
        values = values.where(values.map(lambda x: math.isfinite(x)))
        if column == 'market_cap':
            values = values.where(values > 0)
        # 整列不可用时停止生成计划，避免虚构财务数据后买入。
        if values.notna().sum() == 0:
            return pd.DataFrame()
        result[column] = values.fillna(values.mean())
    result['size_rank'] = result['market_cap'].rank(ascending=True, method='average')
    result['roe_rank'] = result['roe'].rank(ascending=False, method='average')
    result['score'] = result['size_rank'] + result['roe_rank']
    return result.sort_values(['score', 'code']).reset_index(drop=True)


def select_targets(context, ranked, current):
    """依排名选可买满最小申报数量的标的；持仓在涨跌停时仍可保留。"""
    slot = context.portfolio.total_value * (1 - g.cash_buffer) / g.hold_num
    held = held_positions(context)
    targets = []
    for code in ranked['code']:
        quote = current[code]
        if quote.paused or not valid_price(quote.last_price):
            continue
        if code not in held:
            if at_price_limit(quote):
                continue
            if slot < quote.last_price * min_buy_shares(code) * 1.003 + 5:
                continue
        targets.append(code)
        if len(targets) == g.hold_num:
            break
    return targets


def prepare_plan(context):
    today = context.current_dt.date()
    if g.last_prepare_date == today:
        return
    g.last_prepare_date = today
    g.buy_submit_count = 0
    set_costs(context)
    due = g.session_count % g.rebalance_days == 0
    g.session_count += 1
    if not due:
        return

    reference_date = context.previous_date
    current = get_current_data()
    codes = get_index_stocks(g.index, date=reference_date)
    pool = filter_stock_pool(context, codes, current)
    if not pool:
        log.warn('候选池为空，本轮保留原计划，不按空数据清仓。')
        return

    # 仅查询必要字段；date取T-1可见快照，不用statDate取尚未公布的报告。
    q = query(valuation.code, valuation.market_cap, indicator.roe).filter(
        valuation.code.in_(pool)
    )
    ranked = rank_factors(get_fundamentals(q, date=reference_date))
    if ranked.empty:
        log.warn('因子数据不可用，本轮保留原计划。')
        return
    targets = select_targets(context, ranked, current)
    if not targets:
        log.warn('没有满足交易条件的目标，本轮保留原计划。')
        return

    g.target_codes = targets
    g.target_value = context.portfolio.total_value * (1 - g.cash_buffer) / g.hold_num
    g.plan_date = today
    g.has_plan = True
    log.info('双因子调仓：数据截至%s，目标%d只，每只目标金额%.2f，代码%s' % (
        reference_date, len(targets), g.target_value, ','.join(targets)))


def execute_reductions(context):
    """先卖落选股，调仓日再减超配股；无法卖出者后续交易日继续尝试。"""
    if not g.has_plan:
        return
    current = get_current_data()
    open_codes = {item.security for item in get_open_orders().values()}
    is_plan_day = g.plan_date == context.current_dt.date()
    for code, position in held_positions(context).items():
        if code in open_codes:
            continue
        target = g.target_value if code in g.target_codes else 0.0
        if target > 0 and not is_plan_day:
            continue
        quote = current[code]
        if quote.paused or not valid_price(quote.last_price):
            continue
        if valid_price(quote.low_limit) and quote.last_price <= quote.low_limit + 0.0001:
            continue
        if position.closeable_amount <= 0:
            continue
        shares = position.total_amount + position.locked_amount
        value = shares * quote.last_price
        if value <= target:
            continue
        # 可卖数量是实际限制，不会在买入当天假设可以清仓。
        unsellable = py_builtins.max(0, shares - position.closeable_amount)
        target = py_builtins.max(target, unsellable * quote.last_price)
        if target > 0 and value - target < quote.last_price * 100:
            continue
        result = submit_target(code, target, quote, is_buy=False)
        if result is not None:
            log.info('提交减仓 %s，目标市值%.2f；实际成交以持仓为准。' % (code, target))


def execute_buys(context):
    """只在调仓日加仓；保留旧仓也占持股名额和资金，不额外扩张组合。"""
    g.last_buy_callback_date = context.current_dt.date()
    if not g.has_plan or g.plan_date != context.current_dt.date():
        if not g.has_plan:
            log.warn('买入回调已执行，但尚无有效调仓计划，跳过买入。')
        return
    portfolio = context.portfolio
    current = get_current_data()
    held = held_positions(context)
    open_orders = list(get_open_orders().values())
    open_codes = {item.security for item in open_orders}
    open_buys = [item for item in open_orders if item.is_buy]
    occupied = set(held) | {item.security for item in open_buys}
    # 预算、最小申报量和目标市值统一使用本次行情，避免账户估值滞后时反向下单。
    # 聚宽环境可能注入NumPy同名函数；np.any(生成器)对空仓也为真，不能用它做此判断。
    invalid_codes = [code for code in held if not valid_price(current[code].last_price)]
    if invalid_codes:
        log.warn('买入跳过：持仓行情无效，无法核对仓位预算：%s' % ','.join(invalid_codes))
        return
    gross = py_builtins.sum(position_value(position, current[code].last_price)
                            for code, position in held.items())
    # 未完成买单同样占用总仓位预算，不能靠重复委托绕过限制。
    for item in open_buys:
        price = current[item.security].last_price
        if not valid_price(price):
            log.warn('买入跳过：未完成买单%s行情无效。' % item.security)
            return
        gross += py_builtins.max(0, item.amount - item.filled) * price
    room = py_builtins.max(0.0, portfolio.total_value * (1 - g.cash_buffer) - gross)
    budget = py_builtins.min(portfolio.available_cash * 0.995, room)
    log.info('买入回调：计划日=%s，目标%d只，可用现金%.2f，已占仓位%.2f，可买预算%.2f。' % (
        g.plan_date, len(g.target_codes), portfolio.available_cash, gross, budget))
    counts = dict(pending=0, slots=0, quote=0, limit=0, minimum=0, rejected=0, submitted=0)
    for code in g.target_codes:
        if code in open_codes:
            counts['pending'] += 1
            continue
        if code not in occupied and len(occupied) >= g.hold_num:
            counts['slots'] += 1
            continue
        quote = current[code]
        if quote.paused or not valid_price(quote.last_price):
            counts['quote'] += 1
            continue
        if at_price_limit(quote):
            counts['limit'] += 1
            continue
        old_value = position_value(held[code], quote.last_price) if code in held else 0.0
        addition = py_builtins.min(g.target_value - old_value, budget)
        # 科创板每笔买单均至少200股，已有仓位的追加买入也一样。
        minimum = min_buy_shares(code)
        if addition < quote.last_price * minimum * 1.003 + 5:
            counts['minimum'] += 1
            continue
        log.info('准备买入%s：现价%.2f，原持仓市值%.2f，本次增配%.2f。' % (
            code, quote.last_price, old_value, addition))
        result = submit_target(code, old_value + addition, quote, is_buy=True)
        if result is None:
            counts['rejected'] += 1
            log.warn('买入委托未创建：%s，目标市值%.2f；请核对相邻聚宽order日志。' % (
                code, old_value + addition))
            continue
        # 订单成功提交也先占预算；不把Order返回值记作已成交持仓。
        budget = py_builtins.max(
            0.0, budget - addition - py_builtins.max(5.0, addition * 0.0003))
        occupied.add(code)
        counts['submitted'] += 1
        g.buy_submit_count += 1
        log.info('提交加仓 %s，目标市值%.2f；实际成交以持仓为准。' % (
            code, old_value + addition))
    log.info('买入检查：已提交%d，未创建%d，待成交跳过%d，名额占满%d，行情/停牌%d，'
             '涨跌停%d，增配不足最小申报金额%d。' % (
                 counts['submitted'], counts['rejected'], counts['pending'], counts['slots'],
                 counts['quote'], counts['limit'], counts['minimum']))


def retry_plan(context):
    execute_reductions(context)
    execute_buys(context)


def report_execution(context):
    """调仓日盘后核对回调与真实持仓，委托提交不等于成交。"""
    today = context.current_dt.date()
    if g.plan_date != today:
        return
    callback_ran = g.last_buy_callback_date == today
    log.info('调仓执行核对：买入回调=%s，今日买入委托提交%d次，实际持仓%d只，可用现金%.2f。' % (
        callback_ran, g.buy_submit_count, len(held_positions(context)),
        context.portfolio.available_cash))
    if not callback_ran:
        log.warn('调仓计划已生成，但今日买入回调未执行，请核对initialize中的run_daily注册。')
