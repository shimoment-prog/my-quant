"""Task lifecycle, shared public feeds and independently persisted accounts."""
from __future__ import annotations

import copy
import threading
import time
import uuid

from .engine import CODE_STRATEGY_ID, INTERVAL_MS, PaperEngine, validate_config, validate_manual
from .market import BinancePublicClient, MarketFeed, MarketDataError

DEFAULT_ACCOUNT = {"initial_capital": 10000, "sizing": "margin", "order_amount": 200,
                   "leverage": 10, "fee_percent": .05, "slippage_ticks": 0}
CODE_STRATEGY = {
    "id": CODE_STRATEGY_ID, "kind": "code", "name": "EMA / SMA / RSI 同向交叉关键K",
    "version": "1.0.0", "params": {"prior_bars": 3, "exit_model": "rr15"},
    "description": "橙色EMA10、白色SMA10、RSI14；连续同向后交叉，从下一根起等待关键K。支持四种退出。",
}
MANUAL_TEMPLATE = {
    "id": "builtin_ema_sma_rsi", "kind": "manual", "name": "双均线与RSI（简单模板）", "version": "1",
    "description": "同根已收盘K的均线交叉与RSI过滤；可复制修改，不等同于同向关键K代码策略。",
    "definition": {
        "indicators": [{"id": "ema", "type": "EMA", "length": 10, "source": "close"},
                       {"id": "sma", "type": "SMA", "length": 10, "source": "close"},
                       {"id": "rsi", "type": "RSI", "length": 14, "source": "close"}],
        "long": {"enabled": True, "logic": "all", "conditions": [
            {"left": "ema", "op": "cross_up", "right": "sma"}, {"left": "rsi", "op": "gt", "right": 50}]},
        "short": {"enabled": True, "logic": "all", "conditions": [
            {"left": "ema", "op": "cross_down", "right": "sma"}, {"left": "rsi", "op": "lt", "right": 50}]},
        "long_exit": {"enabled": False, "logic": "all", "conditions": []},
        "short_exit": {"enabled": False, "logic": "all", "conditions": []},
        "exit": {"stop_type": "percent", "stop_percent": 1, "stop_indicator": "ema", "reward_risk": 1.5},
    },
}


def now_ms():
    return int(time.time() * 1000)


def numeric_candle(bar):
    # The transport preserves original decimal strings; the indicator engine
    # uses validated finite numbers and Decimal(str(price)) for tick rounding.
    return {**bar, **{key: float(bar[key]) for key in ("open", "high", "low", "close", "volume")}}


class Runtime:
    def __init__(self, task, state=None):
        self.task = copy.deepcopy(task)
        self.engine = PaperEngine(task["config"], state)
        self.lock = threading.RLock()
        self.partial = copy.deepcopy(task.get("display_partial"))
        self.last_save = 0.0
        self.recovery_retry_at = 0.0
        self.start_retry_scheduled = False
        self.deleted = False
        self.chart_dirty = copy.deepcopy(self.engine.state["bars"])


class Manager:
    def __init__(self, store, client=None, feed_factory=MarketFeed, online=True):
        self.store, self.client, self.feed_factory = store, client or BinancePublicClient(), feed_factory
        self.lock = threading.RLock()
        self.tasks, self.feeds = {}, {}
        self.closed = threading.Event()
        self.market = {"symbols": store.get_setting("market_symbols", []), "status": "connecting", "error": None}
        for task, state in self.store.load_tasks():
            migration_events = []
            if "manual_paused" not in task:
                intent = self.store.manual_pause_intent(task["id"])
                task["manual_paused"] = intent if intent is not None else task["status"] == "paused"
                migration_events.append(self._event("pause_policy_updated",
                    "暂停原因已区分：行情恢复后自动继续；用户手动暂停保持",
                    {"manual_paused": task["manual_paused"], "inferred_from_full_history": intent is not None}))
            task.setdefault("recovery_in_progress", False)
            task["recovery_requires_review"] = False
            rt = Runtime(task, state)
            self.tasks[task["id"]] = rt
            self._save(rt, migration_events)
        if online:
            threading.Thread(target=self.refresh_market, name="market-catalog", daemon=True).start()
            for rt in list(self.tasks.values()):
                if rt.task["status"] in {"running", "paused", "starting"} or (
                        rt.task["status"] == "error" and rt.engine.state["position"]):
                    # Restoring an account must not manufacture fills during downtime.
                    rt.task["recovery_in_progress"] = True
                    self._sync_status(rt)
                    self._spawn_start(rt, restoring=True)
                elif rt.task["status"] == "stopped":
                    self._capture_final_bar(rt)

    def refresh_market(self):
        try:
            symbols = self.client.symbols()
            self.market = {"symbols": symbols, "status": "connected", "error": None}
            if not self.closed.is_set():
                self.store.set_setting("market_symbols", symbols)
        except Exception as exc:
            self.market = {**self.market, "status": "error", "error": str(exc)}

    def strategies(self):
        return copy.deepcopy([CODE_STRATEGY, MANUAL_TEMPLATE] + self.store.strategies())

    def save_strategy(self, body, identifier=None):
        if not isinstance(body, dict):
            raise ValueError("策略设置必须为对象")
        name = body.get("name", "")
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("策略名称需要1至100个字符")
        definition = validate_manual(body.get("definition"))
        with self.lock:
            version = int(self.store.strategy(identifier)["version"]) + 1 if identifier else 1
            identifier = identifier or "manual_" + uuid.uuid4().hex
            item = {"id": identifier, "kind": "manual", "name": name.strip(), "version": str(version),
                    "definition": definition, "description": "手动指标条件策略", "created_at_ms": now_ms()}
            self.store.save_strategy(item)
        return item

    def _strategy_snapshot(self, supplied):
        if not isinstance(supplied, dict):
            raise ValueError("请选择策略")
        identifier = supplied.get("id")
        if identifier == CODE_STRATEGY_ID:
            if str(supplied.get("version", "1.0.0")) != "1.0.0":
                raise ValueError("代码策略版本不存在")
            return {**copy.deepcopy(CODE_STRATEGY), "params": supplied.get("params", CODE_STRATEGY["params"])}
        if identifier == MANUAL_TEMPLATE["id"]:
            return copy.deepcopy(MANUAL_TEMPLATE)
        item = self.store.strategy(identifier, supplied.get("version"))
        return copy.deepcopy(item)

    def _config(self, body, identifier):
        if not isinstance(body, dict):
            raise ValueError("任务设置必须为对象")
        config = {key: copy.deepcopy(body.get(key)) for key in ("name", "symbol", "interval")}
        config.update(id=identifier, strategy=self._strategy_snapshot(body.get("strategy")),
                      account=body.get("account", DEFAULT_ACCOUNT))
        return validate_config(config)

    def create(self, body):
        identifier = uuid.uuid4().hex
        config = self._config(body, identifier)
        task = {"id": identifier, "name": config["name"], "symbol": config["symbol"],
                "interval": config["interval"], "config": config, "status": "draft",
                "created_at_ms": now_ms(), "started_at_ms": None, "last_bar_time_ms": None,
                "last_quote_time_ms": None, "end_requested": False, "end_action": None,
                "manual_paused": False, "recovery_in_progress": False, "pause_reason": None,
                "connection": {"status": "disconnected", "message": "尚未启动", "last_event_ms": None}}
        rt = Runtime(task)
        with self.lock:
            self.tasks[identifier] = rt
        with rt.lock:
            self._save(rt, [self._event("task_created", "独立模拟任务已保存；尚未开始接收信号")])
        if body.get("start") is True:
            self.action(identifier, "start")
        return {"id": identifier, "task": self.summary(rt)}

    def update(self, identifier, body):
        rt = self._get(identifier)
        with rt.lock:
            self._ensure_present(rt)
            if rt.task["status"] != "draft":
                raise ValueError("已运行的任务使用固定快照，请复制任务后调整")
            config = self._config(body, identifier)
            rt.task.update(config=config, name=config["name"], symbol=config["symbol"], interval=config["interval"])
            rt.engine = PaperEngine(config)
            self._save(rt, [self._event("task_updated", "草稿配置已更新")])
        if body.get("start") is True:
            self.action(identifier, "start")
        return {"id": identifier, "task": self.summary(rt)}

    def copy_task(self, identifier, body):
        rt = self._get(identifier)
        with rt.lock:
            self._ensure_present(rt)
            config = copy.deepcopy(rt.task["config"])
        config["name"] = body.get("name") or config["name"] + " · 对照"
        config["start"] = False
        return self.create(config)

    def _get(self, identifier):
        with self.lock:
            rt = self.tasks.get(identifier)
        if rt is None or rt.deleted:
            raise KeyError("任务不存在")
        return rt

    @staticmethod
    def _event(kind, message, data=None):
        return {"type": kind, "time_ms": now_ms(), "message": message, "data": data or {}}

    @staticmethod
    def _ensure_present(rt):
        if rt.deleted:
            raise KeyError("任务不存在")

    def _save(self, rt, events=()):
        # Asynchronous final-candle work or a previously captured shutdown
        # reference must not recreate a task after its deletion committed.
        with rt.lock:
            if rt.deleted:
                return
            rt.task["display_partial"] = copy.deepcopy(rt.partial)
            self.store.save(rt.task, rt.engine.snapshot(), events, rt.chart_dirty)
            rt.chart_dirty = []
            rt.last_save = time.monotonic()

    def summary(self, rt):
        with rt.lock:
            self._ensure_present(rt)
            return {**copy.deepcopy(rt.task), "account": rt.engine.account_view()}

    def list_tasks(self):
        with self.lock:
            tasks = list(self.tasks.values())
        results = []
        for rt in tasks:
            try:
                results.append(self.summary(rt))
            except KeyError:
                continue
        return results

    def detail(self, identifier):
        rt = self._get(identifier)
        with rt.lock:
            self._ensure_present(rt)
            result = rt.engine.view()
            result["task"] = copy.deepcopy(rt.task)
            if result.get("position"):
                result["trades"] = result["trades"] + [copy.deepcopy(result["position"])]
            preview_metadata = None
            # Roll back to the last confirmed indicator state for every
            # intrabar preview. Only on_bar may commit it to strategy state.
            if rt.partial:
                bar = rt.partial
                if not result["chart"]["candles"] or bar["open_time_ms"] // 1000 > result["chart"]["candles"][-1]["time"]:
                    result["chart"]["candles"].append({"time": bar["open_time_ms"] // 1000,
                        **{key: bar[key] for key in ("open", "high", "low", "close", "volume")},
                        "closed": bar.get("closed", False), "context_only": bar.get("context_only", False)})
                    if not bar.get("closed", False) and not bar.get("context_only", False):
                        values = rt.engine.preview_indicators(bar)
                        ready = {key: value for key, value in values.items() if value is not None}
                        if ready:
                            preview_time = bar["open_time_ms"] // 1000
                            preview_metadata = {"time": preview_time, "values": ready, "confirmed": False}
                            for series in result["chart"]["indicators"]:
                                if series["id"] in ready:
                                    point = {"time": preview_time, "value": ready[series["id"]], "preview": True}
                                    series["data"].append(point)
                                    series["preview"] = {"time": preview_time, "value": point["value"], "confirmed": False}
            result["logs"] = self.store.logs(identifier)
            result["metadata"].update(gap_policy="补K只推进指标；缺口不追溯成交，行情恢复后自动等待新信号；手动暂停保持",
                                       last_price=rt.engine.state["last_price"],
                                       market_source=rt.task["connection"].get("source", "not_connected"))
            result["metadata"]["tail_candle_context_only"] = bool(rt.partial and rt.partial.get("context_only"))
            result["metadata"]["indicator_preview"] = preview_metadata
            return result

    def _capture_final_bar(self, rt):
        """Preserve the actual exchange candle containing a final intrabar fill.

        It is chart context only. It never advances frozen strategy state or
        creates orders, and incomplete OHLC is explicitly marked incomplete.
        """
        with rt.lock:
            if rt.deleted:
                return
            stamp = rt.engine.state["last_quote_timestamp_ms"]
            last_close = rt.engine.state["last_bar_close_ms"]
            if stamp is None or last_close is None:
                return
            step = INTERVAL_MS[rt.task["interval"]]
            opened = stamp // step * step
            if opened < last_close:
                return
            config = copy.deepcopy(rt.task["config"])
        def capture():
            try:
                rows = self.client.klines(config["symbol"], config["interval"], limit=1,
                                          start_ms=opened, end_ms=opened + step - 1)
                current = self.client.server_time()
                if not rows or rows[0]["open_time_ms"] != opened:
                    return
                candle = dict(numeric_candle(rows[0]), context_only=True,
                              closed=rows[0]["close_time_ms"] + 1 <= current)
                with rt.lock:
                    if self.closed.is_set() or rt.deleted or rt.task["status"] != "stopped":
                        return
                    rt.partial = candle
                    if candle["closed"]:
                        rt.chart_dirty.append(dict(candle, indicators={}))
                    self._save(rt)
            except Exception:
                # The last received partial is already persisted. A network
                # failure must not change the closed account or invent OHLC.
                return
        threading.Thread(target=capture, name="final-candle-" + rt.task["id"][:8], daemon=True).start()

    def chart(self, identifier, before=None, around=None, limit=500):
        rt = self._get(identifier)
        with rt.lock:
            self._ensure_present(rt)
            bars, more = self.store.candles(identifier, before, around, limit)
            specs = rt.engine.indicators
        colors = ["#ff9f43", "#d8e2f0", "#a78bfa", "#2dd4bf", "#60a5fa"]
        candles = [{"time": b["open_time_ms"] // 1000, "closed": True,
                    **{key: b[key] for key in ("open", "high", "low", "close", "volume")}} for b in bars]
        indicators = [{"id": spec["id"], "name": spec["type"] + str(spec["length"]), "type": spec["type"],
            "pane": "rsi" if spec["type"] == "RSI" else "main", "color": colors[i % len(colors)],
            "data": [{"time": b["open_time_ms"] // 1000, "value": b["indicators"][spec["id"]]}
                     for b in bars if b["indicators"].get(spec["id"]) is not None]}
            for i, spec in enumerate(specs)]
        return {"candles": candles, "indicators": indicators, "has_more": more}

    def action(self, identifier, action):
        rt = self._get(identifier)
        should_start = should_detach = False
        with rt.lock:
            self._ensure_present(rt)
            status = rt.task["status"]
            if action == "start":
                if status not in {"draft", "error"}:
                    raise ValueError("请对草稿启动；已结束任务请复制创建新任务")
                rt.task["status"] = "starting"
                rt.task["pause_reason"] = "connection"
                rt.task["recovery_in_progress"] = True
                if status == "draft":
                    rt.task["end_requested"] = False
                    rt.task["manual_paused"] = False
                should_start = True
                events = [self._event("starting", "正在加载合约限制和历史K线，预热期间不下单")]
            elif action == "pause":
                if status not in {"running", "paused"}:
                    raise ValueError("只有运行中任务可暂停开新仓")
                rt.task["manual_paused"] = True
                self._sync_status(rt)
                events = rt.engine.cancel_setup("用户暂停开新仓") + [self._event("paused", "已暂停新开仓，现有持仓继续管理")]
            elif action == "resume":
                if status != "paused" or rt.task.get("end_requested"):
                    raise ValueError("只有未请求结束的暂停任务可恢复")
                if rt.task["connection"]["status"] != "connected" or rt.task["recovery_in_progress"]:
                    raise ValueError("行情尚未恢复，请等待连接正常后恢复开仓")
                rt.task["manual_paused"] = False
                rt.task["recovery_requires_review"] = False
                self._sync_status(rt)
                events = rt.engine.cancel_setup("恢复后等待新信号") + [self._event("resumed", "已恢复开新仓，等待新的触发")]
            elif action in {"stop", "close"}:
                if status not in {"running", "paused", "error"}:
                    raise ValueError("该任务当前不能结束")
                events = rt.engine.cancel_setup("任务请求结束，取消尚未成交的开仓")
                rt.task["end_requested"] = True
                if action == "close":
                    rt.task["end_action"] = "close"
                elif rt.task.get("end_action") != "close":
                    rt.task["end_action"] = "stop"
                if rt.engine.state["position"]:
                    rt.task["status"] = "paused"
                    rt.task["pause_reason"] = "ending"
                    if action == "close":
                        events += rt.engine.close_position("manual_stop")
                    events += [self._event("ending", "等待下一实时报价平仓后结束" if action == "close" else "停止开新仓，待现有持仓退出后结束")]
                else:
                    rt.task["status"] = "stopped"
                    rt.task["pause_reason"] = None
                    rt.task["recovery_in_progress"] = False
                    should_detach = True
                    events += [self._event("stopped", "任务已结束，保留完整账户与交易记录")]
            else:
                raise ValueError("不支持的任务操作")
            self._save(rt, events)
        if should_start:
            self._spawn_start(rt)
        if should_detach:
            self._detach(rt)
        return {"id": identifier, "task": self.summary(rt)}

    def _spawn_start(self, rt, restoring=False):
        threading.Thread(target=self._start, args=(rt, restoring), name="start-" + rt.task["id"][:8], daemon=True).start()

    def _schedule_start_retry(self, rt, restoring):
        with rt.lock:
            if rt.start_retry_scheduled or self.closed.is_set() or rt.deleted or rt.task["status"] in {"draft", "stopped"}:
                return
            rt.start_retry_scheduled = True
        def retry():
            if self.closed.wait(5):
                return
            with rt.lock:
                rt.start_retry_scheduled = False
                if self.closed.is_set() or rt.deleted or rt.task["status"] in {"draft", "stopped"}:
                    return
            self._start(rt, restoring)
        threading.Thread(target=retry, name="retry-start-" + rt.task["id"][:8], daemon=True).start()

    def _sync_status(self, rt):
        """Derive execution availability from current intent while holding rt.lock."""
        task = rt.task
        if task["status"] in {"draft", "stopped"}:
            task["pause_reason"] = None
            return
        if task["status"] == "error":
            task["pause_reason"] = "error"
            return
        if task.get("end_requested"):
            task.update(status="paused", pause_reason="ending")
        elif task.get("manual_paused"):
            task.update(status="paused", pause_reason="manual")
        elif task.get("recovery_in_progress") or task["connection"]["status"] != "connected":
            task.update(status="paused", pause_reason="connection")
        else:
            task.update(status="running", pause_reason=None)

    def _start(self, rt, restoring=False):
        try:
            if self.closed.is_set() or rt.deleted:
                return
            config = rt.task["config"]
            server_now = self.client.server_time()
            filters = {k: float(v) for k, v in self.client.filters(config["symbol"]).items()
                       if k in {"tick_size", "qty_step", "min_qty", "min_notional", "max_qty"} and v is not None}
            with rt.lock:
                if rt.deleted:
                    return
                initialized = rt.engine.state["initialized"]
            if not initialized:
                bars = [numeric_candle(bar) for bar in self.client.klines(config["symbol"], config["interval"], limit=601)]
                completed = [bar for bar in bars if bar["close_time_ms"] + 1 <= server_now]
                with rt.lock:
                    if self.closed.is_set() or rt.deleted or rt.task["status"] == "stopped":
                        return
                    events = rt.engine.bootstrap(completed, filters, server_now)
                    rt.chart_dirty += copy.deepcopy(rt.engine.state["bars"])
                    rt.partial = next((bar for bar in bars if bar["close_time_ms"] + 1 > server_now), None)
                    rt.task["last_bar_time_ms"] = rt.engine.state["last_bar_close_ms"]
                    rt.task["started_at_ms"] = rt.task["started_at_ms"] or server_now
                    self._save(rt, events)
            else:
                self._reconcile(rt, server_now, "后台重启或任务恢复")
                with rt.lock:
                    rt.engine.state["filters"] = filters
            with rt.lock:
                if self.closed.is_set() or rt.deleted or rt.task["status"] == "stopped":
                    return
                rt.task["recovery_in_progress"] = True
                rt.task["connection"] = {"status": "connecting", "message": "正在连接币安实时行情", "last_event_ms": None}
                self._sync_status(rt)
                self._save(rt, [self._event("restored" if restoring else "ready",
                    "运行状态已恢复；行情补齐后按手动暂停设置继续" if restoring else "预热完成，等待连接正常后的新信号")])
            self._attach(rt)
        except MarketDataError as exc:
            if not self.closed.is_set():
                with rt.lock:
                    if rt.deleted or rt.task["status"] in {"draft", "stopped"}:
                        return
                    rt.task["recovery_in_progress"] = True
                    rt.task["connection"] = {"status": "recovering", "message": "初始化/恢复行情暂时失败，将自动重试：" + str(exc),
                                              "last_event_ms": now_ms()}
                    self._sync_status(rt)
                    events = rt.engine.cancel_setup("行情恢复请求失败，清除旧入场信号")
                    self._save(rt, events + [self._event("start_retry", "行情请求暂时失败，5秒后自动重试", {"error": str(exc)})])
                self._schedule_start_retry(rt, restoring)
        except Exception as exc:
            if not self.closed.is_set():
                self._fail(rt, str(exc))

    def _reconcile(self, rt, server_now=None, reason="实时行情断线恢复"):
        if self.closed.is_set() or rt.deleted:
            return
        config = rt.task["config"]
        step = INTERVAL_MS[config["interval"]]
        with rt.lock:
            cursor = rt.engine.state["last_bar_close_ms"]
            if cursor is None or rt.deleted or rt.task["status"] in {"draft", "stopped"}:
                return
            rt.task["recovery_in_progress"] = True
            self._sync_status(rt)
            events = rt.engine.cancel_setup(reason + "：清除未成交入场")
            # Bar exits issued before the interruption are stale too. Explicit
            # user close-and-end intent is requeued after reconciliation.
            if rt.task.get("end_action") == "close" and rt.engine.state["position"]:
                events += rt.engine.close_position("manual_stop")
            else:
                rt.engine.state["pending_exit"] = None
            self._save(rt, events)
        server_now = self.client.server_time() if server_now is None else server_now
        last_boundary = server_now // step * step
        count = 0
        while cursor < last_boundary:
            bars = [numeric_candle(bar) for bar in self.client.klines(config["symbol"], config["interval"], limit=1500,
                                      start_ms=cursor, end_ms=last_boundary - 1)]
            completed = [b for b in bars if cursor <= b["open_time_ms"] and b["close_time_ms"] + 1 <= last_boundary]
            if not completed or completed[0]["open_time_ms"] != cursor:
                raise ValueError("无法补齐K线缺口，任务保持错误状态以免使用缺失指标")
            for bar in completed:
                with rt.lock:
                    if self.closed.is_set() or rt.deleted or rt.task["status"] in {"draft", "stopped"}:
                        return
                    events = rt.engine.on_bar(bar, server_now, allow_entries=False, recovery=True)
                    if rt.task.get("end_action") == "close" and rt.engine.state["position"]:
                        events += rt.engine.close_position("manual_stop")
                    rt.chart_dirty.append(copy.deepcopy(rt.engine.state["bars"][-1]))
                    rt.task["last_bar_time_ms"] = rt.engine.state["last_bar_close_ms"]
                    self._sync_status(rt)
                    self._save(rt, events)
                cursor = bar["close_time_ms"] + 1
                count += 1
            if count > 100000:
                raise ValueError("离线时间过长，请检查恢复进度后重启任务")
        with rt.lock:
            if self.closed.is_set() or rt.deleted or rt.task["status"] in {"draft", "stopped"}:
                return
            events = rt.engine.cancel_setup(reason + "：清除未成交信号")
            if rt.task.get("end_action") == "close" and rt.engine.state["position"]:
                events += rt.engine.close_position("manual_stop")
            if count:
                events += [self._event("data_gap", "已补齐%d根K线；不回补缺口交易，恢复后只等待新信号" % count)]
            was_connection_paused = rt.task.get("pause_reason") == "connection"
            rt.task["recovery_in_progress"] = False
            rt.task["recovery_requires_review"] = False
            self._sync_status(rt)
            if was_connection_paused and rt.task["status"] == "running":
                events.append(self._event("auto_resumed", "行情与指标已恢复，清除旧信号后自动等待新信号"))
            self._save(rt, events)

    def _attach(self, rt):
        key = (rt.task["symbol"], rt.task["interval"])
        with rt.lock:
            if self.closed.is_set() or rt.deleted or rt.task["status"] in {"stopped", "draft"}:
                return
            with self.lock:
                pair = self.feeds.get(key)
                new = pair is None
                if new:
                    pair = {"tasks": set(), "connection": {"status": "connecting", "message": "正在连接公开行情", "last_event_ms": None},
                            "feed": self.feed_factory(*key, on_event=lambda k, d: self._feed_event(key, k, d), client=self.client)}
                    self.feeds[key] = pair
                pair["tasks"].add(rt.task["id"])
            if not new:
                rt.task["connection"] = copy.deepcopy(pair["connection"])
                rt.task["recovery_in_progress"] = pair["connection"]["status"] != "connected"
                self._sync_status(rt)
                self._save(rt)
        if new:
            pair["feed"].start()
            with self.lock:
                orphan = self.feeds.get(key) is not pair
            if orphan:
                pair["feed"].stop()

    def _detach(self, rt):
        key = (rt.task["symbol"], rt.task["interval"])
        stop = None
        with self.lock:
            pair = self.feeds.get(key)
            if pair:
                pair["tasks"].discard(rt.task["id"])
                if not pair["tasks"]:
                    stop = self.feeds.pop(key)["feed"]
        if stop:
            stop.stop()
        if rt.task["status"] == "stopped":
            self._capture_final_bar(rt)

    def _fail(self, rt, message):
        with rt.lock:
            if rt.deleted:
                return
            rt.task["status"] = "error"
            rt.task["pause_reason"] = "error"
            rt.task["connection"] = {"status": "error", "message": message, "last_event_ms": now_ms()}
            events = rt.engine.cancel_setup("运行错误：取消未成交开仓")
            self._save(rt, events + [self._event("error", message)])
        # Existing positions still receive prices and protective exits even
        # when a candle/strategy operation failed. Start/retry can reconcile.
        if rt.engine.state["position"]:
            self._attach(rt)

    def _try_reconcile(self, rt, connection=None):
        try:
            self._reconcile(rt)
            return True
        except MarketDataError as exc:
            # A working quote transport with a temporarily failing REST
            # backfill must keep retrying, rather than become a strategy error.
            with rt.lock:
                if rt.deleted or rt.task["status"] in {"draft", "stopped"} or self.closed.is_set():
                    return False
                if connection is not None:
                    rt.task["connection"] = {"source": connection.get("source", "binance_ws"),
                                              "last_event_ms": connection.get("received_ms", now_ms())}
                rt.task["connection"].update(status="recovering", message="行情已重连，正在重试补齐K线：" + str(exc))
                rt.task["recovery_in_progress"] = True
                rt.recovery_retry_at = time.monotonic() + 5
                self._sync_status(rt)
                events = [self._event("recovery_retry", "行情补齐请求暂时失败，将自动重试", {"error": str(exc)})]
                if rt.task.get("end_action") == "close" and rt.engine.state["position"]:
                    events += rt.engine.close_position("manual_stop")
                self._save(rt, events)
            return False

    def _feed_event(self, key, kind, data):
        if self.closed.is_set():
            return
        if kind in {"bar", "partial"}:
            data = numeric_candle(data)
        with self.lock:
            pair = self.feeds.get(key)
            if pair and kind == "connection":
                pair["connection"] = {"status": data["status"], "message": data.get("message", ""),
                                      "last_event_ms": data.get("received_ms", now_ms()),
                                      "source": data.get("source", "binance_ws")}
            targets = [self.tasks[i] for i in pair["tasks"] if i in self.tasks and not self.tasks[i].deleted] if pair else []
        for rt in targets:
            try:
                if kind == "connection" and data.get("status") == "connected":
                    if not self._try_reconcile(rt, data):
                        continue
                elif kind in {"quote", "partial", "bar"}:
                    with rt.lock:
                        retry = (rt.task.get("recovery_in_progress") and rt.task["connection"]["status"] == "recovering" and
                                 rt.task["status"] in {"running", "paused"} and time.monotonic() >= rt.recovery_retry_at)
                    if retry and self._try_reconcile(rt):
                        with rt.lock:
                            if rt.task["status"] not in {"draft", "stopped", "error"}:
                                rt.task["connection"].update(status="connected", message="行情和K线已补齐，继续接收实时数据")
                                self._sync_status(rt)
                                events = [self._event("recovery_complete", "行情与指标补齐完成")]
                                if rt.task["status"] == "running":
                                    events.append(self._event("auto_resumed", "已清除旧信号，自动等待新信号"))
                                self._save(rt, events)
                detach = False
                with rt.lock:
                    if self.closed.is_set() or rt.deleted:
                        return
                    protective_error = rt.task["status"] == "error" and rt.engine.state["initialized"] and kind in {"quote", "partial", "connection"}
                    if rt.task["status"] not in {"running", "paused"} and not protective_error:
                        continue
                    events = []
                    if kind == "connection":
                        was_connection_paused = rt.task.get("pause_reason") == "connection"
                        rt.task["connection"] = {"status": data["status"], "message": data.get("message", ""),
                            "last_event_ms": data.get("received_ms", now_ms()), "source": data.get("source", "binance_ws")}
                        if data["status"] != "connected":
                            events += rt.engine.cancel_setup("行情中断：取消未成交开仓")
                            if not (rt.engine.state["pending_exit"] or {}).get("reason") == "manual_stop":
                                rt.engine.state["pending_exit"] = None
                            rt.task["recovery_in_progress"] = True
                        else:
                            rt.task["recovery_in_progress"] = False
                        self._sync_status(rt)
                        if was_connection_paused and rt.task["status"] == "running":
                            events.append(self._event("auto_resumed", "行情与指标已恢复，清除旧信号后自动等待新信号"))
                        events.append(self._event("connection", data.get("message", data["status"])))
                    elif kind == "partial":
                        rt.partial = data
                    elif kind == "quote":
                        events = rt.engine.on_quote(float(data["price"]), data["timestamp_ms"], data.get("trade_id"),
                                                    max(data.get("received_ms", now_ms()), data["timestamp_ms"]))
                        rt.task["last_quote_time_ms"] = data["timestamp_ms"]
                        rt.task["connection"]["last_event_ms"] = data.get("received_ms", now_ms())
                        if rt.task.get("end_requested") and not rt.engine.state["position"]:
                            rt.task["status"] = "stopped"
                            rt.task["pause_reason"] = None
                            rt.task["recovery_in_progress"] = False
                            rt.task["connection"]["message"] = "任务已结束"
                            detach = True
                            events.append(self._event("stopped", "持仓已结束，任务完成"))
                    elif kind == "bar":
                        if rt.task["recovery_in_progress"]:
                            continue
                        last_close = rt.engine.state["last_bar_close_ms"]
                        if data["open_time_ms"] > last_close:
                            if not self._try_reconcile(rt):
                                continue
                        events += rt.engine.on_bar(data, max(data.get("event_time_ms", now_ms()), data["close_time_ms"] + 1),
                                                   allow_entries=(rt.task["status"] == "running" and
                                                       not rt.task["manual_paused"] and not rt.task["recovery_in_progress"] and
                                                       not rt.task.get("end_requested") and rt.task["connection"]["status"] == "connected"))
                        rt.chart_dirty.append(copy.deepcopy(rt.engine.state["bars"][-1]))
                        rt.task["last_bar_time_ms"] = rt.engine.state["last_bar_close_ms"]
                        if rt.partial and rt.partial["open_time_ms"] <= data["open_time_ms"]:
                            rt.partial = None
                    if events or kind in {"bar", "connection"} or time.monotonic() - rt.last_save > 5:
                        self._save(rt, events)
                if detach:
                    self._detach(rt)
            except Exception as exc:
                self._fail(rt, str(exc))

    def delete(self, identifier):
        rt = self._get(identifier)
        with rt.lock:
            if rt.deleted:
                raise KeyError("任务不存在")
            if rt.task["status"] not in {"draft", "stopped"} or rt.engine.state["position"] or rt.engine.state["pending_order"]:
                raise ValueError("仅可删除无持仓的草稿或已结束任务")
            previous_status = rt.task["status"]
            rt.deleted = True
            rt.task["status"] = "deleted"
            try:
                self.store.delete(identifier)
            except Exception:
                rt.deleted = False
                rt.task["status"] = previous_status
                raise
            with self.lock:
                self.tasks.pop(identifier, None)
                pair = self.feeds.get((rt.task["symbol"], rt.task["interval"]))
                if pair:
                    pair["tasks"].discard(identifier)
        self._detach(rt)

    def shutdown(self):
        self.closed.set()
        with self.lock:
            feeds = [p["feed"] for p in self.feeds.values()]
            self.feeds.clear()
        for feed in feeds:
            feed.stop()
        for rt in list(self.tasks.values()):
            with rt.lock:
                self._save(rt)
