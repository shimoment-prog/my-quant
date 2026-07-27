import pandas as pd
import numpy as np

def initialize(context):
    # 设定基准银行为沪深300
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 设定好要交易的股票数量
    g.stocknum = 10
    
    # 设定每天运行 period 函数（开盘时执行）
    run_daily(period, time='09:30') 

def period(context):
    # --- 1. 获取全市场当前市值的排名 ---
    # 获取当天所有A股股票代码
    scodes = get_all_securities(types=['stock']).index.tolist()
    
    # 查询这些股票的市值数据（market_cap 字段）
    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(scodes)
    ).order_by(
        valuation.market_cap.asc() # 按市值从小到大排序
    )
    
    df = get_fundamentals(q)
    
    # 【修复点】过滤掉停牌的股票，正确的属性是 .paused
    current_data = get_current_data()
    df = df[df['code'].apply(lambda x: not current_data[x].paused)]
    
    # 取出市值最小的前 stocksnum 只股票作为目标买入列表
    target_stocks = df['code'].head(g.stocknum).tolist()
    
    # --- 2. 卖出逻辑 ---
    # 获取当前持仓的股票列表
    current_holdings = list(context.portfolio.positions.keys())
    
    # 若已持有的股票不在目标买入列表中（说明市值不够小了），则卖出
    for stock in current_holdings:
        if stock not in target_stocks:
            order_target(stock, 0)
            print(f"清仓不符合小市值条件的股票: {stock}")

    # --- 3. 买入逻辑 ---
    # 如果有需要新买入的股票，平分账户的总资产
    if len(target_stocks) > 0:
        # 每只股票目标分配的资金 = 账户当前总资产 / 目标股票总数
        target_value = context.portfolio.total_value / g.stocknum
        
        # 将目标股票买入到对应的权重（内部会自动处理已持有的股票加减仓）
        for stock in target_stocks:
            order_target_value(stock, target_value)
            print(f"调仓/买入目标股票: {stock}, 目标价值: {target_value}")