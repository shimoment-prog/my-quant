# ETHUSDT 三天回测复核

打开 `eth-three-day-review.html`。文件已内嵌全部图表、数据和报告，可离线查看。

- 默认“逐笔 K 线”：选交易编号，使用上一笔/下一笔，检查图下11项条件；可切三天全图并显示所有仓位框。
- “Archify 回测报告”：结果、每日盈亏、入场流程、执行口径和验收清单。
- 时间：北京时间2026-11-15 00:00至2026-11-18 00:00，ETHUSDT USD-M永续，5分钟。
- 24笔、8胜16负；净盈亏−42.354749165 USDT。未计资金费率等，完整边界见报告。

## 生成与验证

`candidate.archify.md`与`daily.csv`是Archify输入；`backtest-report.html`是官方finalize输出。对应delivery/finalize文件保留生成校验凭证。

`eth-three-day-review.html`是自定义外壳，内嵌报告源文件和独立交互图。外壳添加主题及高度适配样式，未改写磁盘上的Archify报告；外壳不属于官方finalize验证范围。

组合页面的独立浏览器检查在`browser-review-final/review.json`：24笔条件、切换、完整仓位框、深浅主题、桌面/手机宽度、离线运行和零JavaScript错误。截图与生成物SHA256绑定。

脚本：`../../strategy/ema_ma_rsi_key_candle/build_archify_review.py`。图表使用TradingView Lightweight Charts 4.2.3，本地仓位标注不是账户中的原生绘图对象。
