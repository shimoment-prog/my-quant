"""Deterministic broker/strategy tests. No network or exchange account needed."""
import copy
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from engine import PaperEngine, validate_config, validate_manual, INTERVAL_MS


STEP = INTERVAL_MS["4h"]
FILTERS = {"tick_size": .01, "qty_step": .001, "min_qty": .001, "min_notional": 5}


def manual_definition():
    return {"indicators": [{"id": "ema", "type": "EMA", "length": 10},
                            {"id": "sma", "type": "SMA", "length": 10},
                            {"id": "rsi", "type": "RSI", "length": 14}],
            "long": {"enabled": True, "logic": "all", "conditions": [{"left": "close", "op": "gt", "right": 0}]},
            "short": {"enabled": False}, "long_exit": {"enabled": False}, "short_exit": {"enabled": False},
            "exit": {"stop_type": "percent", "stop_percent": 1, "reward_risk": 1.5}}


def config(kind="manual", mode="rr15", task="A"):
    strategy = {"id": "manual" if kind == "manual" else "ema_ma_rsi_key_candle_same_direction",
                "kind": kind, "version": "1.0.0", "params": {"prior_bars": 3, "exit_model": mode}}
    if kind == "manual":
        strategy["definition"] = manual_definition()
    return {"id": task, "name": task, "symbol": "ETHUSDT", "interval": "4h", "strategy": strategy,
            "account": {"initial_capital": 10000, "sizing": "margin", "order_amount": 200,
                        "leverage": 10, "fee_percent": .05, "slippage_ticks": 0}}


def candle(index, close=100, opened=None, high=None, low=None):
    opened = close if opened is None else opened
    return {"open_time_ms": index * STEP, "close_time_ms": (index + 1) * STEP - 1,
            "open": opened, "high": max(opened, close) + .1 if high is None else high,
            "low": min(opened, close) - .1 if low is None else low, "close": close, "volume": 100}


def boot(cfg=None):
    engine = PaperEngine(cfg or config())
    engine.bootstrap([candle(i) for i in range(200)], FILTERS, 200 * STEP)
    return engine


def enter(engine, price=100):
    events = engine.on_bar(candle(200), 201 * STEP + 10)
    assert any(e["type"] == "entry_signal" for e in events), events
    engine.on_quote(price, 201 * STEP + 11, "entry", 201 * STEP + 12)
    assert engine.view()["position"] is not None
    return engine.view()["position"]


def fixture_bar(index, ema, sma, rsi=60, opened=103, close=105, low=102.5, high=106):
    return dict(candle(index, close, opened, high, low), indicators={"ema": ema, "sma": sma, "rsi": rsi})


def setup_fixture(engine, side=1):
    # Four strict changes (N=3 plus crossing bar), using five line-value points.
    values = [(90, 95), (92, 96), (94, 97), (96, 98), (102, 100)]
    if side == -1:
        values = [(200-e, 200-s) for e, s in values]
    bars = [fixture_bar(196+i, e, s, 60 if side == 1 else 40) for i, (e, s) in enumerate(values)]
    engine.state["bars"] = bars
    engine.state["last_bar_open_ms"] = bars[-1]["open_time_ms"]
    engine.state["last_bar_close_ms"] = bars[-1]["close_time_ms"] + 1
    return bars[-1]


def fake_position(engine, side=1, mode="rr15", activated=False):
    # Open via the same deferred broker used by public on_bar; just bypass the
    # unrelated entry signal in tests dedicated to exit ordering.
    engine.state["pending_order"] = {"side": side, "signal_time_ms": 200 * STEP,
                                     "signal_received_ms": 200 * STEP,
                                     "signal_bar_open_ms": 199 * STEP,
                                     "entry_reference": 100, "initial_stop": 95 if side == 1 else 105,
                                     "target": (107.5 if side == 1 else 92.5) if mode == "rr15" else None,
                                     "activation_level": None if mode == "rr15" else (107.5 if side == 1 else 92.5),
                                     "exit_model": mode, "audit": {"checks": []}}
    engine.on_quote(100, 200 * STEP, "open")
    engine.state["position"]["trail_active"] = activated
    return engine.state["position"]


class ValidationTests(unittest.TestCase):
    def test_config_and_manual_are_copied_and_normalized(self):
        raw = config()
        norm = validate_config(raw)
        norm["strategy"]["definition"]["indicators"][0]["length"] = 20
        self.assertEqual(raw["strategy"]["definition"]["indicators"][0]["length"], 10)
        self.assertEqual(validate_config(config("code"))["strategy"]["params"]["prior_bars"], 3)

    def test_nonfinite_boolean_unknown_and_invalid_values_rejected(self):
        for field, value in [("initial_capital", math.nan), ("order_amount", math.inf),
                             ("leverage", True), ("leverage", 2.5), ("fee_percent", -.1),
                             ("slippage_ticks", -1)]:
            raw = config(); raw["account"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_config(raw)
        for prior in (2, 11, True):
            raw = config("code"); raw["strategy"]["params"]["prior_bars"] = prior
            with self.assertRaises(ValueError): validate_config(raw)
        raw = config("code"); raw["strategy"]["id"] = "arbitrary_python"
        with self.assertRaises(ValueError): validate_config(raw)
        raw = config(); raw["interval"] = "13m"
        with self.assertRaises(ValueError): validate_config(raw)

    def test_manual_reference_and_stop_validation(self):
        for mutate in (lambda d: d["indicators"].append(dict(d["indicators"][0])),
                       lambda d: d["long"]["conditions"][0].update(right="missing"),
                       lambda d: d["exit"].update(stop_type="indicator", stop_indicator="rsi"),
                       lambda d: d["long"]["conditions"][0].update(op="between", right=70, upper=30),
                       lambda d: d["long"].update(conditions=[])):
            definition = manual_definition(); mutate(definition)
            with self.assertRaises(ValueError): validate_manual(definition)

    def test_unicode_contract_symbols_and_invalid_characters(self):
        for symbol in ("ETHUSDT","币安人生USDT","1000中文_USDT"):
            raw=config();raw["symbol"]=symbol
            self.assertEqual(validate_config(raw)["symbol"],symbol)
        for symbol in ("USDT","ETH/USDT","../ETHUSDT","ETH USDT"):
            raw=config();raw["symbol"]=symbol
            with self.assertRaises(ValueError):validate_config(raw)


class DataAndIndicatorTests(unittest.TestCase):
    def test_bootstrap_never_opens_historical_positions(self):
        engine = boot()
        self.assertIsNone(engine.view()["position"])
        self.assertIsNone(engine.view()["pending_order"])
        self.assertEqual(engine.view()["trades"], [])
        with self.assertRaises(ValueError): engine.bootstrap([candle(i) for i in range(200)], FILTERS, 200 * STEP)

    def test_warmup_future_gaps_and_duplicate_bars(self):
        for bars, now in [([candle(i) for i in range(199)], 200*STEP),
                          ([candle(i) for i in range(200)], 199*STEP),
                          ([candle(i) for i in range(199)] + [candle(200)], 201*STEP)]:
            with self.assertRaises(ValueError): PaperEngine(config()).bootstrap(bars, FILTERS, now)
        engine = boot()
        self.assertEqual(engine.on_bar(candle(199), 200*STEP), [])
        with self.assertRaises(ValueError): engine.on_bar(candle(201), 202*STEP)
        with self.assertRaises(ValueError): engine.on_bar(candle(200), 201*STEP-1)

    def test_incremental_indicators_match_archived_formulas(self):
        engine = PaperEngine(config())
        prices = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
                  45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28]
        rows = [engine._advance(candle(i, price)) for i, price in enumerate(prices)]
        self.assertIsNone(rows[13]["rsi"])
        self.assertAlmostEqual(rows[14]["rsi"], 70.4641350211, places=8)
        self.assertAlmostEqual(rows[9]["sma"], sum(prices[:10])/10, places=12)
        ema = prices[0]
        for price in prices[1:]: ema = 2/11 * price + 9/11 * ema
        self.assertAlmostEqual(rows[-1]["ema"], ema, places=12)

    def test_persistence_and_history_rollover_keep_indicator_seed(self):
        engine = boot()
        for i in range(200, 1510):
            engine.on_bar(candle(i, 100 + (i % 17) / 10), (i+1)*STEP, allow_entries=False)
        restored = PaperEngine(config(), json.loads(json.dumps(engine.snapshot())))
        bar = candle(1510, 103)
        self.assertEqual(engine.on_bar(bar, 1511*STEP, False), restored.on_bar(bar, 1511*STEP, False))
        self.assertEqual(engine.snapshot(), restored.snapshot())
        self.assertEqual(len(engine.snapshot()["bars"]), 1500)
        # Compare to an uninterrupted stream whose UI history never controlled
        # the recursive indicator state.
        all_bars = [candle(i) for i in range(200)] + [candle(i, 100+(i % 17)/10) for i in range(200,1510)] + [bar]
        reference = PaperEngine(config())
        for item in all_bars: reference._advance(reference._candle(item))
        self.assertEqual(engine.snapshot()["indicator_state"], reference.snapshot()["indicator_state"])


class IndicatorPreviewTests(unittest.TestCase):
    def test_repeated_partials_recalculate_without_committing_any_state(self):
        engine = boot()
        # Keep meaningful broker/setup state present: the preview must not
        # cancel it, fill it, create a new signal, or alter the account/history.
        engine.on_bar(candle(200), 201 * STEP + 10)
        engine.state["setup"] = {"side": 1, "trigger_bar_open_ms": 200 * STEP}
        baseline = engine.snapshot()
        high = candle(201, close=120, opened=100)
        low = candle(201, close=90, opened=100)
        first = engine.preview_indicators(high)
        second = engine.preview_indicators(low)
        third = engine.preview_indicators(high)
        self.assertNotEqual(first["ema"], second["ema"])
        self.assertEqual(first, third)
        self.assertEqual(engine.snapshot(), baseline)
        # Result dictionaries do not expose the persisted recursion either.
        first["ema"] = -1
        self.assertEqual(engine.preview_indicators(high), third)
        self.assertEqual(engine.snapshot(), baseline)

    def test_preview_matches_confirming_same_ohlc_and_close_advances_once(self):
        engine = boot(config("code"))
        baseline = engine.snapshot()
        partial = candle(200, close=103, opened=101, high=104, low=100)
        preview = engine.preview_indicators(partial)
        # Partial has a future scheduled closing time, which is valid for a
        # preview. A real on_bar call still rejects it before that close.
        with self.assertRaises(ValueError):
            engine.on_bar(partial, 200 * STEP + 100)
        self.assertEqual(engine.snapshot(), baseline)
        clone = PaperEngine(config("code"), baseline)
        clone.on_bar(partial, 201 * STEP, allow_entries=False)
        self.assertEqual(preview, clone.snapshot()["bars"][-1]["indicators"])
        for close in (101, 110, 103):
            engine.preview_indicators(candle(200, close=close, opened=101))
        engine.on_bar(partial, 201 * STEP, allow_entries=False)
        self.assertEqual(engine.snapshot(), clone.snapshot())
        confirmed = engine.snapshot()
        self.assertEqual(engine.on_bar(partial, 201 * STEP), [])
        self.assertEqual(engine.snapshot(), confirmed)
        self.assertEqual(engine.preview_indicators(partial), {})

    def test_manual_lengths_and_all_ohlc_sources_match_committed_values(self):
        cfg = config()
        specs = []
        for source in ("open", "high", "low", "close"):
            for kind, length in (("EMA", 3), ("SMA", 7), ("RSI", 5)):
                specs.append({"id": kind.lower() + "_" + source,
                              "type": kind, "length": length, "source": source})
        cfg["strategy"]["definition"]["indicators"] = specs
        engine = PaperEngine(cfg)
        rows = [candle(i, close=100 + (i % 7), opened=99 + (i % 5),
                       high=110 + (i % 3), low=90 - (i % 4)) for i in range(200)]
        engine.bootstrap(rows, FILTERS, 200 * STEP)
        partial = candle(200, close=107, opened=101, high=112, low=89)
        baseline = engine.snapshot()
        preview = engine.preview_indicators(partial)
        clone = PaperEngine(cfg, baseline)
        clone.on_bar(partial, 201 * STEP, allow_entries=False)
        self.assertEqual(preview, clone.snapshot()["bars"][-1]["indicators"])
        self.assertEqual(engine.snapshot(), baseline)
        # Source selection is meaningful, rather than silently using close for
        # every displayed line. EMA3 has alpha=0.5.
        for source in ("open", "high", "low", "close"):
            key = "ema_" + source
            expected = .5 * partial[source] + .5 * baseline["indicator_state"][key]["value"]
            self.assertAlmostEqual(preview[key], expected)
        self.assertEqual(len(preview), 12)

    def test_unready_indicators_remain_none_during_previews(self):
        cfg = config()
        cfg["strategy"]["definition"]["indicators"] = [
            {"id": "ema_long", "type": "EMA", "length": 500},
            {"id": "sma_long", "type": "SMA", "length": 500},
            {"id": "rsi_long", "type": "RSI", "length": 500}]
        engine = boot(cfg)
        baseline = engine.snapshot()
        for close in (110, 90, 120, 100):
            preview = engine.preview_indicators(candle(200, close=close))
            self.assertIsNotNone(preview["ema_long"])
            self.assertIsNone(preview["sma_long"])
            self.assertIsNone(preview["rsi_long"])
        self.assertEqual(engine.snapshot(), baseline)

    def test_uninitialized_stale_and_gap_bars_are_not_previewed(self):
        self.assertEqual(PaperEngine(config()).preview_indicators(candle(0)), {})
        engine = boot()
        baseline = engine.snapshot()
        for index in (0, 198, 199, 201, 210):
            self.assertEqual(engine.preview_indicators(candle(index)), {})
        self.assertEqual(engine.snapshot(), baseline)
        invalid = candle(200)
        invalid["high"] = 50
        with self.assertRaises(ValueError): engine.preview_indicators(invalid)
        invalid = candle(200)
        invalid["volume"] = math.nan
        with self.assertRaises(ValueError): engine.preview_indicators(invalid)
        self.assertEqual(engine.snapshot(), baseline)


class BrokerTests(unittest.TestCase):
    def test_signal_waits_for_quote_received_after_confirmation(self):
        engine = boot()
        engine.on_bar(candle(200), 201*STEP+50)
        self.assertIsNotNone(engine.view()["pending_order"])
        self.assertIsNone(engine.view()["position"])
        engine.on_quote(100, 201*STEP+49, "old", 201*STEP+60)
        self.assertIsNone(engine.view()["position"])
        engine.on_quote(100.1, 201*STEP+51, "new", 201*STEP+61)
        p = engine.view()["position"]
        self.assertEqual(p["entry_reference"], 100)
        self.assertEqual(p["entry_fill"], 100.1)
        self.assertEqual(p["entry_time_ms"], 201*STEP+51)

    def test_gap_past_bracket_rejects_and_consumes_signal(self):
        for price in (98, 102):
            engine = boot(); engine.on_bar(candle(200), 201*STEP)
            events = engine.on_quote(price, 201*STEP+1, "gap")
            self.assertEqual(events[0]["type"], "entry_rejected")
            self.assertIsNone(engine.view()["pending_order"])
            self.assertIsNone(engine.view()["position"])

    def test_accounting_qty_fees_and_isolation(self):
        a, b = boot(config(task="A")), boot(config(task="B"))
        p = enter(a)
        self.assertEqual(p["quantity"], 20)
        self.assertEqual(p["margin_used"], 200)
        self.assertEqual(p["entry_fee"], 1)
        self.assertEqual(a.view()["account"]["balance"], 9999)
        self.assertEqual(b.view()["account"]["balance"], 10000)
        a.on_quote(102, 201*STEP+20, "target")
        t = a.view()["trades"][0]
        self.assertEqual(t["exit_fill"],101.5)
        self.assertEqual(t["gross_pnl"], 30)
        self.assertAlmostEqual(t["exit_fee"], 1.015)
        self.assertAlmostEqual(t["net_pnl"], 27.985)
        self.assertAlmostEqual(a.view()["account"]["balance"], 10027.985)
        self.assertEqual(a.view()["account"]["win_rate"], 100)
        self.assertEqual(len(b.view()["trades"]), 0)

    def test_notional_sizing_does_not_multiply_leverage_twice(self):
        cfg = config(); cfg["account"].update(sizing="notional", order_amount=500, leverage=10)
        p = enter(boot(cfg))
        self.assertEqual(p["entry_notional"], 500)
        self.assertEqual(p["margin_used"], 50)

    def test_lightweight_account_view_matches_full_view(self):
        engine=boot();enter(engine)
        self.assertEqual(engine.account_view(),engine.view()["account"])
        account=engine.account_view();account["balance"]=0
        self.assertNotEqual(engine.account_view()["balance"],0)

    def test_funding_and_minimum_rejection_no_cash_mutation(self):
        for account, filters in [({"initial_capital": 100}, FILTERS),
                                 ({}, dict(FILTERS, min_notional=5000)),
                                 ({}, dict(FILTERS, min_qty=100)),
                                 ({}, dict(FILTERS, max_qty=1))]:
            cfg = config(); cfg["account"].update(account)
            engine = PaperEngine(cfg)
            engine.bootstrap([candle(i) for i in range(200)], filters, 200*STEP)
            engine.on_bar(candle(200), 201*STEP)
            engine.on_quote(100, 201*STEP+1, "rejected")
            self.assertIsNone(engine.view()["position"])
            self.assertIsNone(engine.view()["pending_order"])
            self.assertEqual(engine.view()["account"]["balance"], cfg["account"]["initial_capital"])

    def test_stale_and_duplicate_ticks_do_not_double_book(self):
        engine = boot(); enter(engine)
        stamp = 201*STEP+20
        engine.on_quote(102, stamp, "exit")
        self.assertEqual(engine.on_quote(102, stamp, "exit"), [])
        self.assertEqual(engine.on_quote(80, stamp-1, "stale"), [])
        self.assertEqual(len(engine.view()["trades"]), 1)
        state = json.loads(json.dumps(engine.snapshot()))
        restored = PaperEngine(config(), state)
        self.assertEqual(restored.on_quote(102, stamp, "exit"), [])
        self.assertEqual(restored.snapshot(), engine.snapshot())

    def test_local_clock_lag_does_not_reject_valid_market_quote(self):
        engine=boot(); enter(engine)
        engine.on_quote(100.5,201*STEP+30,"clock-lag",201*STEP+25)
        self.assertEqual(engine.snapshot()["last_quote_received_ms"],201*STEP+25)
        self.assertEqual(engine.snapshot()["last_quote_timestamp_ms"],201*STEP+30)

    def test_pause_cancels_entry_but_manages_existing_position(self):
        engine = boot(); enter(engine)
        engine.on_bar(candle(201), 202*STEP, allow_entries=False)
        engine.on_quote(98, 202*STEP+1, "stop")
        self.assertEqual(engine.view()["trades"][0]["exit_reason"], "stop")
        engine.on_bar(candle(202), 203*STEP, allow_entries=False)
        self.assertIsNone(engine.view()["pending_order"])

    def test_recovery_ohlc_never_reconstructs_fills_or_activation(self):
        engine = boot(config("code", "trail_ema")); fake_position(engine, mode="trail_ema")
        engine.on_bar(candle(200, 100, high=120, low=80), 201*STEP, recovery=True)
        self.assertEqual(len(engine.view()["trades"]), 0)
        self.assertFalse(engine.view()["position"]["trail_active"])
        self.assertIsNone(engine.view()["pending_order"])

    def test_close_command_queues_next_price_and_stop_has_priority(self):
        engine = boot(); fake_position(engine)
        engine.close_position()
        self.assertIsNotNone(engine.view()["position"])
        engine.on_quote(94, 200*STEP+1, "close")
        self.assertEqual(engine.view()["trades"][0]["exit_reason"], "stop")

    def test_same_bar_reentry_is_blocked(self):
        engine = boot(); enter(engine)
        engine.on_quote(98, 201*STEP+20, "stop")
        engine.on_bar(candle(201), 202*STEP)
        self.assertIsNone(engine.view()["pending_order"])
        engine.on_bar(candle(202), 203*STEP)
        self.assertIsNotNone(engine.view()["pending_order"])


class CodeStrategyTests(unittest.TestCase):
    def test_cross_needs_n_plus_one_strict_changes_and_later_key(self):
        engine = boot(config("code"))
        crossing = setup_fixture(engine)
        side, audit, events = engine._code_signal(crossing, 201*STEP)
        self.assertEqual(side, 0)
        self.assertEqual(engine.state["setup"]["directional_changes_checked"], 4)
        self.assertEqual(events[0]["type"], "setup_armed")
        key = fixture_bar(201, 104, 101, low=104.5, opened=105, close=106, high=107)
        engine.state["bars"].append(key)
        side, audit, _ = engine._code_signal(key, 202*STEP)
        self.assertEqual(side, 1)
        self.assertTrue(all(row["pass"] for row in audit["checks"]))
        self.assertEqual(audit["trigger"]["trigger_bar_open_ms"], 200*STEP)

    def test_flat_or_mixed_cross_rejected_permanently(self):
        for change in ("flat", "mixed"):
            engine = boot(config("code")); crossing = setup_fixture(engine)
            if change == "flat": engine.state["bars"][1]["indicators"]["sma"] = 95
            else: engine.state["bars"][1]["indicators"]["ema"] = 89
            engine._code_signal(crossing, 201*STEP)
            self.assertIsNone(engine.state["setup"])
            key = fixture_bar(201, 104, 101, low=104.5, opened=105, close=106, high=107)
            engine.state["bars"].append(key)
            self.assertEqual(engine._code_signal(key, 202*STEP)[0], 0)

    def test_n10_requires_twelve_points_for_eleven_changes(self):
        cfg=config("code");cfg["strategy"]["params"]["prior_bars"]=10
        for total,expected in ((11,False),(12,True)):
            engine=boot(cfg)
            values=[(50+i,60+i) for i in range(total-1)]+[(80,72)]
            rows=[fixture_bar(200-total+1+i,e,s) for i,(e,s) in enumerate(values)]
            engine.state["bars"]=rows
            engine._code_signal(rows[-1],201*STEP)
            self.assertEqual(engine.state["setup"] is not None,expected)

    def test_short_requires_red_candle_full_upper_wick_and_rsi(self):
        engine = boot(config("code")); crossing = setup_fixture(engine, -1)
        engine._code_signal(crossing, 201*STEP)
        for rsi, opened, close, high, expected in [(40,95,96,97,0), (40,96,95,98,0),
                                                   (50,96,95,97,0), (30,96,95,97,-1)]:
            key = fixture_bar(201, 98, 100, rsi, opened, close, 94, high)
            engine.state["bars"] = engine.state["bars"][:5] + [key]
            self.assertEqual(engine._code_signal(key, 202*STEP)[0], expected)

    def test_long_rsi_50_excluded_70_included_and_key_direction_unneeded(self):
        engine = boot(config("code")); crossing = setup_fixture(engine)
        engine._code_signal(crossing, 201*STEP)
        # EMA falls on the key; only the trigger's joint direction matters.
        for rsi, expected in ((50,0), (70,1), (70.1,0)):
            key = fixture_bar(201, 101, 100.5, rsi, opened=103, close=104, low=102, high=105)
            engine.state["bars"] = engine.state["bars"][:5] + [key]
            self.assertEqual(engine._code_signal(key, 202*STEP)[0], expected)

    def test_invalid_bracket_keeps_setup_but_quantity_rejection_consumes(self):
        engine = boot(config("code")); crossing = setup_fixture(engine)
        engine._code_signal(crossing, 201*STEP)
        key = fixture_bar(201,104.004,101,60,104.005,104.006,104.0045,105)
        engine.state["bars"].append(key)
        side, audit, _ = engine._code_signal(key,202*STEP)
        self.assertEqual(side, 1)
        engine._queue_entry(side,audit,key,202*STEP)
        self.assertIsNone(engine.view()["pending_order"])
        self.assertIsNotNone(engine.state["setup"])


class ExitTests(unittest.TestCase):
    def test_activation_is_real_quote_only_and_persistent(self):
        engine = boot(config("code", "ema_turn")); fake_position(engine, mode="ema_turn")
        engine.on_bar(candle(200, 101, high=110, low=99), 201*STEP)
        self.assertFalse(engine.view()["position"]["trail_active"])
        engine.on_quote(108, 201*STEP+1, "activation")
        self.assertTrue(engine.view()["position"]["trail_active"])
        engine.on_quote(101, 201*STEP+2, "retreat")
        self.assertTrue(engine.view()["position"]["trail_active"])

    def test_trailing_tightens_at_close_not_retroactive_shadow(self):
        engine = boot(config("code", "trail_ema")); fake_position(engine, mode="trail_ema")
        engine.on_quote(108,200*STEP+1,"activate")
        # Old low=99 is below the new EMA stop, but it occurred before the
        # close. It cannot retroactively fill the newly updated order.
        engine.on_bar(candle(200,110,opened=100,high=111,low=99),201*STEP)
        self.assertIsNotNone(engine.view()["position"])
        stop=engine.view()["position"]["stop"]
        self.assertGreater(stop,100)
        engine.on_quote(stop-.01,201*STEP+1,"new-stop")
        self.assertEqual(engine.view()["trades"][0]["exit_reason"],"stop")

    def test_delayed_quote_uses_stop_that_was_active_at_quote_time(self):
        engine=boot(config("code","trail_ema"));fake_position(engine,mode="trail_ema")
        engine.on_quote(108,200*STEP+1,"activate")
        engine.on_bar(candle(200,110,opened=100,high=111,low=99),201*STEP+50)
        new_stop=engine.view()["position"]["stop"]
        engine.on_quote(new_stop-.1,201*STEP+20,"delayed",201*STEP+60)
        self.assertIsNotNone(engine.view()["position"])
        engine.on_quote(new_stop-.1,201*STEP+51,"fresh",201*STEP+61)
        self.assertEqual(engine.view()["trades"][0]["exit_reason"],"stop")

    def test_activation_after_bar_boundary_cannot_change_prior_bar_exit(self):
        engine=boot(config("code","trail_ema"));fake_position(engine,mode="trail_ema")
        engine.on_quote(108,201*STEP+1,"activate-next-bar")
        engine.on_bar(candle(200,110,opened=100,high=111,low=99),201*STEP+10)
        self.assertEqual(engine.view()["position"]["stop"],95)

    def test_slow_and_turn_signal_boundary_and_deferred_fills(self):
        for mode, values, passes in [("ema_slow",(100,104,106),True),
                                     ("ema_slow",(100,104,104),False),
                                     ("ema_slow",(100,104,103),False),
                                     ("ema_turn",(100,104,103),True),
                                     ("ema_turn",(100,104,104),False)]:
            with self.subTest(mode=mode,values=values):
                engine=boot(config("code",mode)); fake_position(engine,mode=mode,activated=True)
                engine.state["bars"]=[fixture_bar(198,values[0],99),fixture_bar(199,values[1],100),fixture_bar(200,values[2],101)]
                engine._close_management(engine.state["bars"][-1],201*STEP)
                self.assertEqual(engine.view()["pending_exit"] is not None,passes)
                self.assertEqual(engine.view()["position"]["stop"],95)
                if passes:
                    self.assertEqual(len(engine.view()["trades"]),0)
                    engine.on_quote(105,201*STEP+1,"close")
                    self.assertEqual(engine.view()["trades"][0]["exit_fill"],105)
                    self.assertEqual(engine.view()["trades"][0]["exit_reason"],mode+"_close")

    def test_stop_precedes_pending_momentum_exit(self):
        engine=boot(config("code","ema_turn")); fake_position(engine,mode="ema_turn",activated=True)
        engine.state["pending_exit"]={"reason":"ema_turn_close","received_ms":200*STEP}
        engine.on_quote(94,200*STEP+1,"stop")
        self.assertEqual(engine.view()["trades"][0]["exit_reason"],"stop")

    def test_manual_conditions_cross_between_wicks_and_exit(self):
        engine=boot()
        prev={"open":99,"high":100,"low":98,"close":99,"ema":100,"rsi":50}
        current={"open":100,"high":103,"low":101,"close":102,"ema":101,"rsi":70}
        cases=[({"left":"close","op":"cross_up","right":"ema"},True),
               ({"left":"rsi","op":"between","right":50,"upper":70,"include_lower":False,"include_upper":True},True),
               ({"left":"close","op":"wick_above","right":"ema"},False),
               ({"op":"bullish"},True),({"op":"bearish"},False)]
        for condition,expected in cases:
            self.assertEqual(engine._condition(condition,current,prev)[0],expected)
        cfg=config(); cfg["strategy"]["definition"]["long_exit"]={"enabled":True,"conditions":[{"op":"bullish"}]}
        engine=boot(cfg); enter(engine)
        engine.on_bar(candle(201,100.2,opened=100),202*STEP)
        self.assertIsNotNone(engine.view()["pending_exit"])
        engine.on_quote(100.3,202*STEP+1,"manual-exit")
        self.assertEqual(engine.view()["trades"][0]["exit_reason"],"manual_close")


if __name__ == "__main__":
    unittest.main()
