"""Account isolation, frozen rule versions, persistence and local HTTP checks."""
import copy
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.paper_trading.backend.service import Manager, MANUAL_TEMPLATE, DEFAULT_ACCOUNT
from app.paper_trading.backend.storage import Store
from app.paper_trading.backend.market import MarketDataError
from app.paper_trading.server import handler_for

STEP = 60000


def bar(index, opened=100, closed=101):
    return {"open_time_ms": index * STEP, "close_time_ms": (index + 1) * STEP - 1,
            "open": str(opened), "close": str(closed), "high": str(max(opened, closed) + 1),
            "low": str(min(opened, closed) - 1), "volume": "10"}


class Client:
    def __init__(self):
        self.bars = [bar(i) for i in range(200)]
        self.clock = 200 * STEP + 1

    def symbols(self):
        return [{"symbol": "ETHUSDT", "base_asset": "ETH", "quote_asset": "USDT", **self.filters("ETHUSDT")}]

    def server_time(self):
        return self.clock

    def filters(self, _symbol):
        return dict(tick_size="0.01", qty_step="0.001", min_qty="0.001", min_notional="1", max_qty="1000")

    def klines(self, _symbol, _interval, limit=500, start_ms=None, end_ms=None):
        return [b for b in self.bars if (start_ms is None or b["open_time_ms"] >= start_ms)
                and (end_ms is None or b["open_time_ms"] <= end_ms)][-limit:]


class Feed:
    created = []

    def __init__(self, symbol, interval, on_event, client=None):
        self.callback, self.stopped = on_event, False
        self.created.append(self)

    def start(self):
        self.callback("connection", {"status": "connecting", "message": "connecting", "received_ms": 1})
        self.callback("connection", {"status": "connected", "message": "connected", "received_ms": 2})

    def stop(self):
        self.stopped = True


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "state.db")
        self.client = Client()
        Feed.created = []
        self.manager = Manager(self.store, self.client, Feed, online=False)
        definition = copy.deepcopy(MANUAL_TEMPLATE["definition"])
        definition["long"]["conditions"] = [{"op": "bullish"}]
        definition["short"]["enabled"] = False
        self.strategy = self.manager.save_strategy({"name": "阳线实验", "definition": definition})

    def tearDown(self):
        self.manager.shutdown()
        self.store.close()
        self.tmp.cleanup()

    def create(self, capital=1000, amount=50, start=True):
        return self.manager.create({"name": "隔离实验", "symbol": "ETHUSDT", "interval": "1m",
            "strategy": self.strategy, "account": {**DEFAULT_ACCOUNT, "initial_capital": capital,
                "order_amount": amount, "leverage": 2}, "start": start})["id"]

    def ready(self, identifier):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            task = self.manager.detail(identifier)["task"]
            if task["connection"]["status"] == "connected":
                self.assertEqual(task["status"], "running")
                return
            if task["status"] == "error":
                self.fail(task["connection"]["message"])
            time.sleep(.005)
        self.fail("task did not initialize")

    def event(self, kind, data):
        self.manager._feed_event(("ETHUSDT", "1m"), kind, data)

    def quote(self, price, stamp, identifier):
        self.event("quote", {"price": str(price), "timestamp_ms": stamp, "trade_id": identifier,
                            "received_ms": stamp + 1, "event_time_ms": stamp})

    def test_initial_connect_keeps_running_and_history_has_no_trades(self):
        identifier = self.create()
        self.ready(identifier)
        detail = self.manager.detail(identifier)
        self.assertEqual(len(detail["chart"]["candles"]), 200)
        self.assertEqual(detail["trades"], [])
        self.assertEqual(detail["account"]["equity"], 1000)

    def test_shared_feed_independent_cash_trades_and_pause(self):
        a, b = self.create(1000, 50), self.create(3000, 100)
        self.ready(a); self.ready(b)
        self.assertEqual(len(Feed.created), 1)
        self.manager.action(b, "pause")
        new = bar(200, 101, 102)
        self.event("bar", {**new, "received_ms": 201 * STEP, "event_time_ms": 201 * STEP})
        self.quote(102.01, 201 * STEP + 1, 1)
        ad, bd = self.manager.detail(a), self.manager.detail(b)
        self.assertIsNotNone(ad["position"])
        self.assertIsNone(bd["position"])
        self.assertLess(ad["account"]["balance"], 1000)
        self.assertEqual(bd["account"]["balance"], 3000)
        self.assertEqual(bd["task"]["status"], "paused")
        self.quote(110, 201 * STEP + 2, 2)
        self.assertEqual(self.manager.detail(a)["account"]["closed_count"], 1)
        self.assertEqual(self.manager.detail(b)["trades"], [])
        self.assertFalse(any(e["type"] == "entry_filled" for e in self.store.logs(b)))

    def test_partial_only_displayed_never_signals(self):
        identifier = self.create(); self.ready(identifier)
        self.event("partial", {**bar(200, 101, 102), "received_ms": 200 * STEP + 1})
        data = self.manager.detail(identifier)
        self.assertFalse(data["chart"]["candles"][-1]["closed"])
        self.assertIsNone(data["pending_order"])
        self.assertEqual(data["task"]["last_bar_time_ms"], 200 * STEP)
        self.manager.shutdown()
        restored = Manager(self.store, self.client, Feed, online=False)
        try:
            self.assertFalse(restored.detail(identifier)["chart"]["candles"][-1]["closed"])
            self.assertEqual(restored.detail(identifier)["chart"]["candles"][-1]["time"], 200 * STEP // 1000)
        finally:
            restored.shutdown()

    def test_current_candle_indicator_previews_update_without_strategy_mutation(self):
        identifier = self.create(); self.ready(identifier)
        rt = self.manager._get(identifier)
        baseline = rt.engine.snapshot()
        log_ids = [e["id"] for e in self.store.logs(identifier)]
        values = []
        for close in (102, 99, 103):
            self.event("partial", {**bar(200, 101, close), "received_ms": 200 * STEP + 2})
            detail = self.manager.detail(identifier)
            preview = detail["metadata"]["indicator_preview"]
            self.assertFalse(preview["confirmed"])
            self.assertEqual(preview["time"], 200 * STEP // 1000)
            for series in detail["chart"]["indicators"]:
                self.assertEqual(series["data"][-1]["time"], preview["time"])
                self.assertTrue(series["data"][-1]["preview"])
                self.assertEqual(series["data"][-1]["value"], preview["values"][series["id"]])
            values.append(preview["values"])
            self.assertEqual(rt.engine.snapshot(), baseline)
            self.assertEqual([e["id"] for e in self.store.logs(identifier)], log_ids)
            self.assertIsNone(detail["pending_order"])
        self.assertGreater(values[0]["ema"], values[1]["ema"])
        self.assertGreater(values[2]["ema"], values[0]["ema"])
        # At close, the exact final preview becomes confirmed once.
        self.event("bar", {**bar(200, 101, 103), "received_ms": 201 * STEP, "event_time_ms": 201 * STEP})
        confirmed = self.manager.detail(identifier)
        self.assertIsNone(confirmed["metadata"]["indicator_preview"])
        self.assertIsNone(rt.partial)
        self.assertEqual(rt.engine.state["bar_count"], baseline["bar_count"] + 1)
        for series in confirmed["chart"]["indicators"]:
            self.assertNotIn("preview", series["data"][-1])
            self.assertEqual(series["data"][-1]["value"], values[-1][series["id"]])

    def test_stale_gap_and_context_only_candles_do_not_preview_indicators(self):
        identifier = self.create(); self.ready(identifier)
        rt = self.manager._get(identifier)
        for index, extra in [(199, {}), (201, {}), (200, {"context_only": True}), (200, {"closed": True})]:
            self.event("partial", {**bar(index, 101, 102), **extra})
            detail = self.manager.detail(identifier)
            self.assertIsNone(detail["metadata"]["indicator_preview"])
            for series in detail["chart"]["indicators"]:
                self.assertNotIn("preview", series)
                self.assertNotIn("preview", series["data"][-1])
        self.assertEqual(rt.engine.state["bar_count"], 200)

    def test_strategy_versions_and_copy_do_not_mutate_running_account(self):
        identifier = self.create(start=False)
        new = self.manager.save_strategy({"name": "新版", "definition": self.strategy["definition"]}, self.strategy["id"])
        self.assertEqual(new["version"], "2")
        self.assertEqual(self.manager.detail(identifier)["task"]["config"]["strategy"]["version"], "1")
        copied = self.manager.copy_task(identifier, {})["id"]
        self.assertNotEqual(copied, identifier)
        self.assertEqual(self.manager.detail(copied)["task"]["status"], "draft")
        self.assertEqual(self.manager.detail(copied)["trades"], [])
        body = copy.deepcopy(self.manager.detail(copied)["task"]["config"])
        body["account"]["initial_capital"] = 9999
        self.manager.update(copied, body)
        self.assertEqual(self.manager.detail(identifier)["account"]["initial_capital"], 1000)

    def test_restore_snapshot_keeps_account_and_indicator_seed(self):
        identifier = self.create(); self.ready(identifier)
        self.quote(101.5, 200 * STEP + 2, 99)
        self.manager.shutdown()
        other = Manager(self.store, self.client, Feed, online=False)
        try:
            self.assertEqual(other.detail(identifier)["chart"], self.manager.detail(identifier)["chart"])
            self.assertEqual(other.detail(identifier)["account"], self.manager.detail(identifier)["account"])
            self.assertEqual(other._get(identifier).engine.state["seen_trade_ids"], ["99"])
        finally:
            other.shutdown()

    def test_recovery_auto_resumes_new_signals_without_backfilling_trades(self):
        identifier = self.create(); self.ready(identifier)
        self.client.bars += [bar(200), bar(201)]
        self.client.clock = 202 * STEP + 1
        self.event("connection", {"status": "reconnecting", "message": "gap", "received_ms": self.client.clock})
        self.event("connection", {"status": "connected", "message": "restored", "received_ms": self.client.clock})
        data = self.manager.detail(identifier)
        self.assertEqual(data["task"]["status"], "running")
        self.assertIsNone(data["task"]["pause_reason"])
        self.assertEqual(data["task"]["last_bar_time_ms"], 202 * STEP)
        self.assertEqual(data["trades"], [])
        self.assertIsNone(data["pending_order"])
        self.assertIn("data_gap", [e["type"] for e in data["logs"]])
        self.assertIn("auto_resumed", [e["type"] for e in data["logs"]])
        self.event("bar", {**bar(202, 101, 102), "received_ms": 203 * STEP, "event_time_ms": 203 * STEP})
        self.assertIsNotNone(self.manager.detail(identifier)["pending_order"])
        self.quote(102.1, 203 * STEP + 1, 1)
        self.assertIsNotNone(self.manager.detail(identifier)["position"])

    def test_manual_pause_remains_through_shared_feed_recovery(self):
        a, b = self.create(), self.create(); self.ready(a); self.ready(b)
        self.manager.action(b, "pause")
        self.client.bars += [bar(200)]
        self.client.clock = 201 * STEP + 1
        self.event("connection", {"status": "reconnecting", "message": "gap"})
        self.assertEqual(self.manager.detail(a)["task"]["pause_reason"], "connection")
        self.assertEqual(self.manager.detail(b)["task"]["pause_reason"], "manual")
        self.event("connection", {"status": "connected", "message": "restored"})
        self.assertEqual(self.manager.detail(a)["task"]["status"], "running")
        self.assertEqual(self.manager.detail(b)["task"]["status"], "paused")
        self.assertTrue(self.manager.detail(b)["task"]["manual_paused"])
        self.manager.action(b, "resume")
        self.assertEqual(self.manager.detail(b)["task"]["status"], "running")

    def test_manual_pause_during_reconcile_is_not_overwritten(self):
        identifier = self.create(); self.ready(identifier)
        self.client.bars += [bar(200)]
        self.client.clock = 201 * STEP + 1
        entered, release = threading.Event(), threading.Event()
        real_klines = self.client.klines
        def blocked(*args, **kwargs):
            if kwargs.get("start_ms") is not None:
                entered.set(); release.wait(2)
            return real_klines(*args, **kwargs)
        self.client.klines = blocked
        worker = threading.Thread(target=self.event, args=("connection", {"status": "connected", "message": "restored"}))
        worker.start()
        self.assertTrue(entered.wait(1))
        self.manager.action(identifier, "pause")
        release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        data = self.manager.detail(identifier)
        self.assertEqual(data["task"]["pause_reason"], "manual")
        self.assertEqual(data["task"]["status"], "paused")
        self.assertIsNone(data["pending_order"])

    def test_disconnect_cancels_stale_signals_even_without_missing_bar(self):
        identifier = self.create(); self.ready(identifier)
        self.event("bar", {**bar(200, 101, 102), "received_ms": 201 * STEP, "event_time_ms": 201 * STEP})
        self.assertIsNotNone(self.manager.detail(identifier)["pending_order"])
        rt = self.manager._get(identifier)
        self.client.clock = 201 * STEP + 1
        self.event("connection", {"status": "reconnecting", "message": "short gap"})
        rt.engine.state["pending_exit"] = {"reason": "ema_turn_close", "received_ms": 201 * STEP}
        self.event("connection", {"status": "connected", "message": "restored"})
        data = self.manager.detail(identifier)
        self.assertEqual(data["task"]["status"], "running")
        self.assertIsNone(data["pending_order"])
        self.assertIsNone(data["pending_exit"])
        self.quote(102.1, 201 * STEP + 2, 1)
        self.assertIsNone(self.manager.detail(identifier)["position"])

    def test_reconnect_does_not_hide_strategy_error_or_skip_position_stop(self):
        identifier = self.create(); self.open_position(identifier)
        self.client.clock = 201 * STEP + 1
        self.manager._fail(self.manager._get(identifier), "strategy error")
        self.event("connection", {"status": "reconnecting", "message": "gap"})
        self.event("connection", {"status": "connected", "message": "restored"})
        self.assertEqual(self.manager.detail(identifier)["task"]["status"], "error")
        self.assertEqual(self.manager.detail(identifier)["task"]["pause_reason"], "error")
        self.quote(90, 201 * STEP + 2, 2)
        self.assertIsNone(self.manager.detail(identifier)["position"])

    def test_legacy_pause_migration_uses_full_control_history(self):
        a, b, c = self.create(), self.create(), self.create()
        self.ready(a); self.ready(b); self.ready(c)
        self.manager.action(b, "pause")
        self.manager.action(c, "pause"); self.manager.action(c, "resume")
        for identifier in (a, b, c):
            rt = self.manager._get(identifier)
            rt.task.pop("manual_paused")
            rt.task["status"] = "paused"
            self.manager._save(rt, [self.manager._event("connection", "reconnecting") for _ in range(300)])
        other = Manager(self.store, self.client, Feed, online=False)
        try:
            self.assertFalse(other.detail(a)["task"]["manual_paused"])
            self.assertTrue(other.detail(b)["task"]["manual_paused"])
            self.assertFalse(other.detail(c)["task"]["manual_paused"])
            self.assertIn("pause_policy_updated", [e["type"] for e in other.detail(b)["logs"]])
        finally:
            other.shutdown()

    def test_restart_auto_recovers_running_task_and_keeps_manual_pause(self):
        a, b = self.create(), self.create(); self.ready(a); self.ready(b)
        self.manager.action(b, "pause")
        self.manager.shutdown()
        other = Manager(self.store, self.client, Feed, online=True)
        try:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if all(other.detail(i)["task"]["connection"]["status"] == "connected" for i in (a, b)):
                    break
                time.sleep(.005)
            self.assertEqual(other.detail(a)["task"]["status"], "running")
            self.assertEqual(other.detail(b)["task"]["status"], "paused")
            self.assertEqual(other.detail(b)["task"]["pause_reason"], "manual")
            self.assertEqual(other.detail(a)["trades"], [])
        finally:
            other.shutdown()

    def test_transient_backfill_failure_retries_and_keeps_protective_quotes(self):
        identifier = self.create(); self.open_position(identifier)
        rt = self.manager._get(identifier)
        self.client.clock = 201 * STEP + 1
        original_clock = self.client.server_time
        def offline():
            raise MarketDataError("temporary network reset")
        self.event("connection", {"status": "reconnecting", "message": "gap"})
        self.client.server_time = offline
        self.event("connection", {"status": "connected", "message": "quote stream recovered"})
        data = self.manager.detail(identifier)
        self.assertEqual(data["task"]["status"], "paused")
        self.assertEqual(data["task"]["pause_reason"], "connection")
        self.assertTrue(data["task"]["recovery_in_progress"])
        # Quotes still protect a position while the Kline REST retry waits.
        self.quote(90, 201 * STEP + 2, 2)
        self.assertIsNone(self.manager.detail(identifier)["position"])
        self.client.server_time = original_clock
        rt.recovery_retry_at = 0
        self.quote(101, 201 * STEP + 3, 3)
        data = self.manager.detail(identifier)
        self.assertEqual(data["task"]["status"], "running")
        self.assertFalse(data["task"]["recovery_in_progress"])
        self.assertIsNone(data["pending_order"])
        self.assertIn("recovery_retry", [e["type"] for e in data["logs"]])

    def test_failed_recovery_never_overrides_new_manual_pause(self):
        identifier = self.create(); self.ready(identifier)
        rt = self.manager._get(identifier)
        original_clock = self.client.server_time
        def offline():
            raise MarketDataError("temporary reset")
        self.client.server_time = offline
        self.event("connection", {"status": "connected", "message": "retry"})
        self.manager.action(identifier, "pause")
        self.client.server_time = original_clock
        rt.recovery_retry_at = 0
        self.quote(101, 200 * STEP + 1, 1)
        data = self.manager.detail(identifier)
        self.assertEqual(data["task"]["connection"]["status"], "connected")
        self.assertEqual(data["task"]["pause_reason"], "manual")
        self.assertEqual(data["task"]["status"], "paused")

    def test_explicit_close_executes_even_when_kline_backfill_is_unavailable(self):
        identifier = self.create(); self.open_position(identifier)
        self.manager.action(identifier, "close")
        self.client.server_time = lambda: (_ for _ in ()).throw(MarketDataError("Kline endpoint down"))
        self.event("connection", {"status": "reconnecting", "message": "gap"})
        self.event("connection", {"status": "connected", "message": "trade stream restored"})
        data = self.manager.detail(identifier)
        self.assertEqual(data["pending_exit"]["reason"], "manual_stop")
        self.assertEqual(data["task"]["pause_reason"], "ending")
        self.quote(102.1, 201 * STEP + 2, 2)
        data = self.manager.detail(identifier)
        self.assertIsNone(data["position"])
        self.assertEqual(data["task"]["status"], "stopped")
        self.assertEqual(data["trades"][-1]["exit_reason"], "manual_stop")

    def test_restart_network_failure_schedules_retry_and_preserves_intent(self):
        a, b = self.create(), self.create(); self.ready(a); self.ready(b)
        self.manager.action(b, "pause")
        self.manager.shutdown()
        original_clock = self.client.server_time
        self.client.server_time = lambda: (_ for _ in ()).throw(MarketDataError("temporary startup reset"))
        retries = []
        with patch.object(Manager, "_schedule_start_retry", side_effect=lambda rt, restoring: retries.append(rt.task["id"])):
            other = Manager(self.store, self.client, Feed, online=True)
            try:
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and len(retries) < 2:
                    time.sleep(.005)
                self.assertEqual(set(retries), {a, b})
                self.assertEqual(other.detail(a)["task"]["pause_reason"], "connection")
                self.assertEqual(other.detail(b)["task"]["pause_reason"], "manual")
                self.assertNotEqual(other.detail(a)["task"]["status"], "error")
                self.client.server_time = original_clock
                other._start(other._get(a), restoring=True)
                other._start(other._get(b), restoring=True)
                self.assertEqual(other.detail(a)["task"]["status"], "running")
                self.assertEqual(other.detail(b)["task"]["pause_reason"], "manual")
            finally:
                other.shutdown()

    def test_stop_detaches_only_when_all_subscribers_end(self):
        a, b = self.create(), self.create(); self.ready(a); self.ready(b)
        self.manager.action(a, "stop")
        self.assertFalse(Feed.created[0].stopped)
        self.manager.action(b, "stop")
        self.assertTrue(Feed.created[0].stopped)
        self.assertEqual(self.manager.detail(a)["task"]["status"], "stopped")

    def test_running_config_is_immutable(self):
        identifier = self.create(); self.ready(identifier)
        with self.assertRaises(ValueError):
            self.manager.update(identifier, self.manager.detail(identifier)["task"]["config"])

    def open_position(self, identifier):
        self.ready(identifier)
        self.event("bar", {**bar(200, 101, 102), "received_ms": 201 * STEP, "event_time_ms": 201 * STEP})
        self.quote(102.01, 201 * STEP + 1, 1)
        self.assertIsNotNone(self.manager.detail(identifier)["position"])

    def test_error_still_executes_protective_stop(self):
        identifier = self.create()
        self.open_position(identifier)
        self.manager._fail(self.manager._get(identifier), "模拟单根K处理失败")
        self.quote(90, 201 * STEP + 2, 2)
        self.assertIsNone(self.manager.detail(identifier)["position"])
        self.assertEqual(self.manager.detail(identifier)["account"]["closed_count"], 1)

    def test_manual_close_survives_recovery_gap(self):
        identifier = self.create()
        self.open_position(identifier)
        self.manager.action(identifier, "close")
        self.client.bars += [bar(200), bar(201)]
        self.client.clock = 202 * STEP + 1
        self.manager._reconcile(self.manager._get(identifier))
        self.quote(102.1, 202 * STEP + 2, 2)
        data = self.manager.detail(identifier)
        self.assertIsNone(data["position"])
        self.assertEqual(data["task"]["status"], "stopped")
        self.assertEqual(data["trades"][-1]["exit_reason"], "manual_stop")

    def test_stop_during_recovery_does_not_resurrect_task(self):
        identifier = self.create(); self.ready(identifier)
        self.client.bars += [bar(200)]
        self.client.clock = 201 * STEP + 1
        entered, release = threading.Event(), threading.Event()
        real_klines = self.client.klines
        def blocked(*args, **kwargs):
            if kwargs.get("start_ms") is not None:
                entered.set(); release.wait(2)
            return real_klines(*args, **kwargs)
        self.client.klines = blocked
        worker = threading.Thread(target=self.manager._reconcile, args=(self.manager._get(identifier),))
        worker.start()
        self.assertTrue(entered.wait(1))
        self.manager.action(identifier, "stop")
        release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.manager.detail(identifier)["task"]["status"], "stopped")
        self.assertEqual(self.manager.feeds, {})
        self.manager._attach(self.manager._get(identifier))
        self.assertEqual(self.manager.feeds, {})

    def test_first_transport_fallback_does_not_pause_new_task(self):
        identifier = self.create(); self.ready(identifier)
        rt = self.manager._get(identifier)
        with rt.lock:
            rt.task["connection"]["status"] = "connecting"
        self.event("connection", {"status": "reconnecting", "message": "首次切换REST", "source": "rest_agg_trades"})
        self.event("connection", {"status": "connected", "message": "REST连接", "source": "rest_agg_trades"})
        self.assertEqual(self.manager.detail(identifier)["task"]["status"], "running")

    def test_historical_chart_paging_and_task_isolation(self):
        a, b = self.create(), self.create(start=False)
        self.ready(a)
        history = self.manager.chart(a, limit=50)
        self.assertEqual(len(history["candles"]), 50)
        self.assertTrue(history["has_more"])
        before = history["candles"][0]["time"]
        older = self.manager.chart(a, before=before, limit=50)
        self.assertLess(older["candles"][-1]["time"], before)
        self.assertTrue(older["indicators"][0]["data"])
        around = self.manager.chart(a, around=100 * STEP // 1000, limit=20)
        self.assertEqual(around["candles"][10]["time"], 100 * STEP // 1000)
        self.assertEqual(self.manager.chart(b)["candles"], [])

    def test_final_execution_candle_is_context_not_future_strategy_input(self):
        identifier = self.create()
        self.open_position(identifier)
        rt = self.manager._get(identifier)
        count = rt.engine.state["bar_count"]
        self.client.bars += [bar(200), bar(201)]
        self.client.clock = 202 * STEP + 1
        self.manager.action(identifier, "close")
        self.quote(102.1, 201 * STEP + 2, 2)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and not (rt.partial and rt.partial.get("context_only")):
            time.sleep(.005)
        self.assertTrue(rt.partial["context_only"])
        self.assertEqual(rt.engine.state["bar_count"], count)
        self.assertEqual(self.manager.detail(identifier)["account"]["closed_count"], 1)
        self.assertTrue(self.manager.detail(identifier)["chart"]["candles"][-1]["context_only"])

    def test_delete_stopped_task_removes_only_its_account_chart_and_logs(self):
        a, b = self.create(), self.create(); self.ready(a); self.ready(b)
        untouched = self.manager.detail(b)
        self.manager.action(a, "stop")
        rt = self.manager._get(a)
        self.assertTrue(self.manager.chart(a)["candles"])
        self.manager.delete(a)
        with self.assertRaises(KeyError):
            self.manager.detail(a)
        self.assertEqual([t["id"] for t in self.manager.list_tasks()], [b])
        self.assertEqual(self.manager.detail(b), untouched)
        self.assertEqual(self.store.logs(a), [])
        self.assertEqual(self.store.candles(a)[0], [])
        self.assertEqual([t[0]["id"] for t in self.store.load_tasks()], [b])
        self.assertTrue(self.store.strategy(self.strategy["id"]))
        # Captured background references cannot reinsert the deleted account.
        self.manager._save(rt, [self.manager._event("late", "stale worker")])
        self.manager._fail(rt, "late failure")
        self.manager._attach(rt)
        self.assertEqual([t[0]["id"] for t in self.store.load_tasks()], [b])
        self.assertEqual(self.store.logs(a), [])

    def test_delete_draft_and_reject_live_or_pending_tasks(self):
        draft = self.create(start=False)
        self.manager.delete(draft)
        with self.assertRaises(KeyError):
            self.manager.delete(draft)
        active = self.create(); self.ready(active)
        with self.assertRaises(ValueError):
            self.manager.delete(active)
        self.manager.action(active, "pause")
        with self.assertRaises(ValueError):
            self.manager.delete(active)
        self.manager.action(active, "resume")
        self.open_position(active)
        self.manager.action(active, "stop")
        with self.assertRaises(ValueError):
            self.manager.delete(active)
        self.assertIsNotNone(self.manager.detail(active)["position"])

    def test_delete_failure_restores_task_for_retry(self):
        identifier = self.create(start=False)
        rt = self.manager._get(identifier)
        with patch.object(self.store, "delete", side_effect=sqlite3.OperationalError("test failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.manager.delete(identifier)
        self.assertFalse(rt.deleted)
        self.assertEqual(self.manager.detail(identifier)["task"]["status"], "draft")
        self.manager.delete(identifier)

    def test_http_delete_removes_draft_but_rejects_running_task(self):
        draft, active = self.create(start=False), self.create()
        self.ready(active)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.manager, 0))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d/api/tasks/" % httpd.server_address[1]
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(urllib.request.Request(base + active, method="DELETE"))
            self.assertEqual(cm.exception.code, 400)
            result = json.load(urllib.request.urlopen(urllib.request.Request(base + draft, method="DELETE")))
            self.assertTrue(result["deleted"])
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(base + draft)
            self.assertEqual(cm.exception.code, 404)
            self.assertEqual(json.load(urllib.request.urlopen(base + active))["task"]["status"], "running")
        finally:
            httpd.shutdown(); httpd.server_close()

    def test_final_candle_worker_finishing_after_delete_does_not_restore_task(self):
        identifier = self.create(); self.open_position(identifier)
        entered, release = threading.Event(), threading.Event()
        original_klines = self.client.klines
        def blocked(*args, **kwargs):
            if kwargs.get("limit") == 1:
                entered.set(); release.wait(2)
            return original_klines(*args, **kwargs)
        self.client.bars += [bar(200), bar(201)]
        self.client.clock = 202 * STEP + 1
        self.client.klines = blocked
        self.manager.action(identifier, "close")
        self.quote(102.1, 201 * STEP + 2, 2)
        self.assertTrue(entered.wait(1))
        rt = self.manager._get(identifier)
        self.manager.delete(identifier)
        release.set()
        self.manager._save(rt)
        self.assertEqual(self.store.load_tasks(), [])
        self.assertEqual(self.store.logs(identifier), [])

    def test_http_contract_rejects_cross_origin_and_invalid_json(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.manager, 0))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d" % httpd.server_address[1]
        try:
            payload = json.load(urllib.request.urlopen(url + "/api/bootstrap"))
            self.assertEqual(payload["tasks"], [])
            self.assertEqual(len(payload["strategies"]), 3)
            request = urllib.request.Request(url + "/api/tasks", data=b'{}', headers={"Content-Type": "application/json", "Origin": "https://example.com"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(request)
            self.assertEqual(cm.exception.code, 403)
            request = urllib.request.Request(url + "/api/tasks", data=b'{"amount":NaN}', headers={"Content-Type": "application/json"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(request)
            self.assertEqual(cm.exception.code, 400)
        finally:
            httpd.shutdown(); httpd.server_close()


if __name__ == "__main__":
    unittest.main()
