# 克隆自聚宽文章：https://www.joinquant.com/post/1399
# 标题：【量化课堂】多因子策略入门
# 作者：JoinQuant量化课堂
#
# 本版参数：持仓 10 只；回测初始资金请在聚宽界面设为 ￥300000
# （资金在平台回测设置里配置，策略代码无法直接改初始资金）
#多因子策略入门
# 建议回测：每天；初始资金 300000


'''
================================================================================
总体回测前
================================================================================
'''

#总体回测前要做的事情
def initialize(context):
    set_params()        #1设置策参数
    set_variables() #2设置中间变量
    set_backtest()   #3设置回测条件
    log.info('策略参数: 持仓=%d只, 调仓间隔=%d日; 请确认回测初始资金为 300000' % (g.N, g.tc))


#1
#设置策参数
def set_params():
    g.tc = 15   # 调仓频率（交易日）
    g.yb = 63   # 样本长度：近 N 日未停牌过滤
    g.N = 10    # 持仓数目（30万资金约每只3万，可覆盖多数成分股价）
    g.factors = ["market_cap", "roe"]  # 小市值 + 高ROE
    # 因子方向：1 表示因子值越小越好，-1 表示越大越好
    g.weights = [[1], [-1]]
    
    
#2
#设置中间变量
def set_variables():
    g.t=0              #记录回测运行的天数
    g.if_trade=False   #当天是否交易
    
    
#3
#设置回测条件
def set_backtest():
    set_option('use_real_price', True)  # 用真实价格交易
    set_option('avoid_future_data', True)
    log.set_level('order', 'error')





'''
================================================================================
每天开盘前
================================================================================
'''

#每天开盘前要做的事情
def before_trading_start(context):
    if g.t%g.tc==0:
        #每g.tc天，交易一次行
        g.if_trade=True 
        # 设置手续费与手续费
        set_slip_fee(context) 
        # 设置可行股票池：获得当前开盘的沪深300股票池并剔除当前或者计算样本期间停牌的股票
        g.all_stocks = set_feasible_stocks(get_index_stocks('000300.XSHG'),g.yb,context)
        # 查询所有财务因子
        g.q = query(valuation,balance,cash_flow,income,indicator).filter(valuation.code.in_(g.all_stocks))
    g.t+=1
    
#4
# 设置可行股票池
# 过滤掉当日停牌的股票,且筛选出前days天未停牌股票
# 输入：stock_list为list类型,样本天数days为int类型，context（见API）
# 输出：list
def set_feasible_stocks(stock_list,days,context):
    # 当日停牌用 get_current_data，避免 get_price 的 panel 废弃警告
    current_data = get_current_data()
    unsuspened_stocks = [s for s in stock_list if not current_data[s].paused]

    # 进一步筛选：近 days 个交易日均未停牌
    feasible_stocks = []
    for stock in unsuspened_stocks:
        paused_hist = attribute_history(
            stock, days, unit='1d', fields=['paused'], skip_paused=False, df=True
        )
        if paused_hist is None or len(paused_hist) == 0:
            continue
        if paused_hist['paused'].sum() == 0:
            feasible_stocks.append(stock)
    return feasible_stocks
    
#5
# 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    log.info(type(context.current_dt))
    
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
        
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
            
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
                
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))




'''
================================================================================
每天交易时
================================================================================
'''

def handle_data(context, data):
    if g.if_trade == True:
        todayStr = str(context.current_dt)[0:10]
        a, b = getRankedFactors(g.factors, todayStr)
        points = np.dot(a, g.weights)
        stock_sort = b[:]
        points, stock_sort = bubble(points, stock_sort)

        # 从排名中挑选能买满 1 手（100股）的标的，不足则向后顺延
        ranked = list(stock_sort.values)
        toBuy = pick_buyable_stocks(context, ranked, g.N)

        # 先卖出不在目标中的持仓，释放现金
        order_stock_sell(context, data, toBuy)

        if len(toBuy) == 0:
            log.info('无足够资金买入一手的候选股，今日跳过开仓')
            g.if_trade = False
            return

        # 按实际可买数量等权，预留约 2% 防手续费导致资金不够
        g.everyStock = context.portfolio.portfolio_value / len(toBuy) * 0.98
        order_stock_buy(context, data, toBuy)
    g.if_trade = False


#6
#获得卖出信号，并执行卖出操作
#输入：context, data，toBuy-list
#输出：none
def order_stock_sell(context, data, toBuy):
    #如果现有持仓股票不在股票池，清空
    list_position = list(context.portfolio.positions.keys())
    for stock in list_position:
        if stock not in toBuy:
            order_target(stock, 0)

#7
# 从因子排名中挑选可开仓（至少 100 股）的股票
def pick_buyable_stocks(context, ranked_stocks, hold_num):
    current_data = get_current_data()
    # 先按目标持仓数估算单票资金
    approx = context.portfolio.portfolio_value / max(hold_num, 1) * 0.98
    selected = []

    for stock in ranked_stocks:
        if len(selected) >= hold_num:
            break
        cd = current_data[stock]
        price = cd.last_price
        if price is None or price != price or price <= 0:
            continue
        if cd.paused:
            continue
        # 涨停通常买不进
        if price >= cd.high_limit * 0.997:
            continue
        # A股开仓至少 100 股：单票资金不够一手则跳过该高价股
        if approx < price * 100:
            continue
        selected.append(stock)

    if not selected:
        return []

    # 用实际入选数量再筛一遍，避免入选变少后资金估算偏差
    value_per = context.portfolio.portfolio_value / len(selected) * 0.98
    return [s for s in selected if value_per >= current_data[s].last_price * 100]


#8
#获得买入信号，并执行买入操作
#输入：context, data，toBuy-list
#输出：none
def order_stock_buy(context, data, toBuy):
    current_data = get_current_data()
    for stock in toBuy:
        price = current_data[stock].last_price
        if price is None or price != price or price <= 0:
            continue
        # 二次校验：分配金额买不足一手则不下单，避免刷 ERROR
        if g.everyStock < price * 100:
            log.info('%s 现价=%.2f，分配=%.2f，不足一手，跳过' % (stock, price, g.everyStock))
            continue
        order_target_value(stock, g.everyStock)


#9
#查找一个元素在数组里面的位置，如果不存在，则返回-1
#输入：元素，对应数组
#输出：-1
def indexOf(e,a):
    for i in range(0,len(a)):
        if e==a[i]:
            return i
    return -1


#10
#取因子数据
#输入：f-全局通用的查询,d-str
#输出：因子数据,股票的代码-dataframe
def getRankedFactors(f,d):
    # 获得股票的基本面数据，这个API里面有，g.q是一个全局通用的查询
    df = get_fundamentals(g.q,d)
    # 为了防止Python里面的浅复制现象，采用循环来定义二维数组
    res = [([0] * len(f)) for i in range(len(df))]
    # 把数据填充到刚才定义的数组里面
    for i in range(0,len(df)):
        for j in range(0,len(f)):
            res[i][j]=df[f[j]][i]
    # 用均值填充NaN值
    fillNan(res)
    # 将数据变成排名
    getRank(res)
    # 返回因子数据和股票的代码（这个是因为沪深300指数成分股一直在变，如果用未来的沪深300指数成分股在之前可能有一些股票还没上市）
    return res,df['code']

#11
#把每列原始数据变成排序的数据
#输入：r-list
#输出：r-list
def getRank(r):
    # 定义一个临时数组记住一开始的顺序
    indexes=list(range(0,len(r)))
    # 对每一列进行冒泡排序
    for k in range(len(r[0])):
        for i in range(len(r)):
            for j in range(i):
                if r[j][k] < r[i][k]:
                    # 交换所有的列以及用于记录一开始的顺序的数组
                    indexes[j], indexes[i] = indexes[i], indexes[j]
                    for l in range(len(r[0])):
                        r[j][l], r[i][l] = r[i][l], r[j][l]
        # 将排序好的因子顺序变成排名
        for i in range(len(r)):
            r[i][k]=i+1
    # 再进行一次冒泡排序恢复一开始的股票顺序
    for i in range(len(r)):
        for j in range(i):
            if indexes[j] > indexes[i]:
                indexes[j], indexes[i] = indexes[i], indexes[j]
                for k in range(len(r[0])):
                    r[j][k], r[i][k] = r[i][k], r[j][k]
    # 因为Python是引用传递，所以其实这个可以不用返回值也行，当然如果你想用另外一个变量来存储排序结果的话可以考虑返回值的方法
    return r

#12
#用均值填充Nan
#输入：m-list
#输出：m-list
def fillNan(m):
    # 计算出因子数据有多少行（行是不同的股票）
    rows=len(m) 
    # 计算出因子数据有多少列（列是不同的因子）
    columns=len(m[0])
    # 这个循环是对每一列进行操作
    for j in range(0,columns):
    # 定义一个临时变量，用来存储每列加总的值
        sum=0.0
        # 定义一个临时变量，用来计算非NaN值的个数
        count=0.0
        # 计算非NaN值的总和和个数
        for i in range(0,rows):
            if not(isnan(m[i][j])):
                sum+=m[i][j]
                count+=1
        # 计算平均值，为了防止全是NaN，如果当整列都是NaN的时候认为平均值是0
        avg=sum/max(count,1)
        for i in range(0,rows):
        # 这个for循环是用来把NaN值填充为刚才计算出来的平均值的
            if isnan(m[i][j]):
                m[i][j]=avg
    return m

#13
#定义一个冒泡排序的函数
#输入：numbers是股票的综合得分-list
#输出：indexes是股票列表-list
def bubble(numbers,indexes):
    for i in range(len(numbers)):
        for j in range(i):
            if numbers[j][0] < numbers[i][0]:
                # 在进行交换的时候同时交换得分以记录哪些股票得分比较高
                numbers[j][0], numbers[i][0] = numbers[i][0], numbers[j][0]
                indexes[j], indexes[i] = indexes[i], indexes[j] 
    return numbers,indexes




'''
================================================================================
每天收盘后
================================================================================
'''
# 每日收盘后要做的事情（本策略中不需要）
def after_trading_end(context):
    return
