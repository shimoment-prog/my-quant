# ETHUSDT 2026年11月10—15日回测复核

打开 `eth-nov10-15-review.html`；已内嵌数据、图表库和Archify报告，可离线查看。

北京时间2026-11-10 00:00至2026-11-16 00:00，包含15日全天。ETHUSDT USD-M永续，5分钟。入场收盘时间含首尾，期末不使用后续K线。

30笔，6胜24负；毛盈亏−32.10243 USDT，费用29.891010955 USDT，净盈亏−61.993440955 USDT；期末9938.006559045 USDT。每次独立从10,000 USDT开始，每笔名义仓位为权益10%。未计资金费率、标记价格触发及强平。

两笔双触退出K按先止损计算：#16（11月13日07:50），#21（11月14日06:00），均北京时间。

## 查看

默认“逐笔 K 线”，选择交易或点上一笔/下一笔。图下显示11项条件核对。“区间全图”显示六天；勾选“显示所有仓位框”查看全部30笔。第二个标签为Archify回测报告。

EMA10白线、SMA10橙线、RSI14。周期指5分钟K线根数。多空框为本地模拟标注，非TradingView账户原生画图对象。

## 数据与验证

原始CSV：`../../strategy/ema_ma_rsi_key_candle/data/ETHUSDT-5m-20261105-20261116.csv`，3168根连续K线，11份官方日ZIP及校验和均验证通过，包含预热。引擎截至11月16日00:00北京，图表显示1800根K，含六天1728根及72根前置参照。

结果：`../../strategy/ema_ma_rsi_key_candle/results/20261110-20261116-chart/`。

独立45位Decimal重算EMA/SMA/RSI、重放信号、首根关键K、出场和数量，30笔逐笔一致，330项检查通过。浏览器证据在`browser-review/review.json`，包含最终HTML哈希、30笔检查、日期、双触说明、60个仓位矩形、深浅主题、桌面/手机宽度和离线运行；无JavaScript错误。

`backtest-report.html`为Archify官方finalize输出。其delivery/finalize凭证只覆盖报告源文件。`eth-nov10-15-review.html`为组合外壳，增加运行时主题与高度适配，已单独检查。

## 复现

在项目根目录运行：

```bash
python3 strategy/ema_ma_rsi_key_candle/build_trade_chart.py --csv strategy/ema_ma_rsi_key_candle/data/ETHUSDT-5m-20261105-20261116.csv --start 2026-11-10T00:00:00+08:00 --end 2026-11-16T00:00:00+08:00 --output-dir strategy/ema_ma_rsi_key_candle/results/20261110-20261116-chart --fragment .archify/explainer-eth-nov10-15-20261118-161211/chart-fragment.html
```

报告输入为本目录`candidate.archify.md`与`daily.csv`。报告由Archify `finalize explainer`生成，再由`build_archify_review.py`组合，传入`--title`与`--period-label`。


## 第二笔关键 K 核对及显示修订

第二笔判定 K 为北京时间11月10日02:20—02:25，开2119.04、收2117.75（阴线），最高2119.36低于SMA2122.681和EMA2122.9150932256，RSI38.4977552963。02:25为该阴线收盘入场时刻，也为下一根阳线的开盘标签。01:45交叉触发K只启动等待。

对照原始CSV复核全部30笔：空单关键K均收跌且最高价低于两线，多单均收涨且最低价高于两线。Pine与Python条件一致。

本次为图表说明修订：选择器显示关键K开盘时间；图前固定展示关键K完整时段、方向、开收盘和影线条件；蓝框突出判定K，蓝点表示收盘成交。触发标记明确为“开始等待”。`summary.json`、`trades.csv`、`trade_audit.json`、`equity.csv`、`report.md`重建后哈希均与修订前相同。

新浏览器证据在`browser-review-key-clarity/`。最新Archify报告finalize凭证在`review-key-clarity/`。修订前HTML与报告凭证在`before-key-clarity/`，旧截图只适用于其旧哈希。
