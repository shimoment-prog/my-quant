"""Independent price, indicator, timing and accounting fixtures."""
import csv
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from backtest import (Candle, Config, Indicator, Position, indicator_series,
                      load_candles, resolve_exit, round_tick, run_backtest,
                      target_for_reference)

STEP = 300000


def bar(index, opened, high, low, close):
    return Candle(index * STEP, opened, high, low, close, 1, (index + 1) * STEP - 1)


def cfg(**kwargs):
    return Config(start_ms=0, end_ms=100 * STEP, **kwargs)


def simulate(bars, indicators, settings=None):
    with patch("backtest.indicator_series", return_value=iter(indicators)):
        return run_backtest(bars, settings or cfg())


class IndicatorTests(unittest.TestCase):
    def test_ema_first_close_and_sma_complete_window(self):
        bars = [bar(i, p, p, p, p) for i, p in enumerate([1, 2, 3])]
        values = list(indicator_series(bars, cfg(ema_length=3, ma_length=3)))
        self.assertEqual([v.ema for v in values], [1, 1.5, 2.25])
        self.assertEqual([v.sma for v in values], [None, None, 2])

    def test_wilder_rsi_seed_and_recursive_average(self):
        bars = [bar(i, p, p, p, p) for i, p in enumerate([1, 2, 1, 3])]
        values = list(indicator_series(bars, cfg(rsi_length=2)))
        self.assertIsNone(values[1].rsi)
        self.assertEqual(values[2].rsi, 50)
        self.assertAlmostEqual(values[3].rsi, 100 - 100 / 6)

    def test_all_flat_rsi_uses_explicit_zero_loss_guard(self):
        values = list(indicator_series([bar(i, 10, 10, 10, 10) for i in range(4)], cfg(rsi_length=2)))
        self.assertEqual(values[-1].rsi, 100)

    def test_future_prices_do_not_change_prefix_indicators(self):
        bars = [bar(i, p, p, p, p) for i, p in enumerate([10, 12, 11, 50, 1])]
        self.assertEqual(list(indicator_series(bars[:3], cfg(rsi_length=2))),
                         list(indicator_series(bars, cfg(rsi_length=2)))[:3])

    def test_price_rounding_half_up(self):
        self.assertEqual(round_tick(98.005, .01), 98.01)

    def test_sma_half_tick_is_not_lost_in_binary_price_sum(self):
        prices = [1900.97, 1900.98] * 5
        bars = [bar(i, p, p, p, p) for i, p in enumerate(prices)]
        last = list(indicator_series(bars, cfg()))[-1]
        self.assertEqual(last.sma, 1900.975)
        self.assertEqual(round_tick(last.sma, .01), 1900.98)

    def test_targets_round_half_tick_up_on_both_sides(self):
        self.assertEqual(target_for_reference(100, 99.99, 1.5, .01), 100.02)
        self.assertEqual(target_for_reference(100, 100.01, 1.5, .01), 99.99)


class FillTests(unittest.TestCase):
    def setUp(self):
        self.long = Position(1, "L1", 0, STEP, 100, 100, 98, 103, 1, .05)
        self.short = Position(-1, "S1", 0, STEP, 100, 100, 102, 97, 1, .05)

    def test_double_touch_long_path_and_conservative_policy(self):
        low_first = bar(1, 100, 104, 97, 101)
        high_first = bar(1, 100, 103, 96, 101)
        self.assertEqual(resolve_exit(self.long, low_first, "tv-path"), (98, "stop_both", True))
        self.assertEqual(resolve_exit(self.long, high_first, "tv-path"), (103, "target_both", True))
        self.assertEqual(resolve_exit(self.long, high_first, "stop-first"), (98, "stop_both", True))

    def test_double_touch_short_path_and_equal_distance_low_first(self):
        self.assertEqual(resolve_exit(self.short, bar(1, 100, 103, 96, 100), "tv-path"),
                         (102, "stop_both", True))
        self.assertEqual(resolve_exit(self.short, bar(1, 100, 104, 96, 100), "tv-path"),
                         (97, "target_both", True))

    def test_long_gaps_use_open_not_order_price(self):
        self.assertEqual(resolve_exit(self.long, bar(1, 97, 99, 96, 98), "stop-first"), (97, "stop_gap", False))
        self.assertEqual(resolve_exit(self.long, bar(1, 104, 105, 102, 103), "stop-first"), (104, "target_gap", False))

    def test_short_gaps_use_open_not_order_price(self):
        self.assertEqual(resolve_exit(self.short, bar(1, 104, 105, 101, 102), "stop-first"), (104, "stop_gap", False))
        self.assertEqual(resolve_exit(self.short, bar(1, 96, 99, 95, 98), "stop-first"), (96, "target_gap", False))


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.bars = [bar(0, 99, 99.5, 98.5, 99), bar(1, 99, 104, 98.5, 100)]
        self.inds = [Indicator(98, 97, 60), Indicator(97, 98, 60)]

    def test_cross_bar_entry_cannot_exit_on_its_earlier_high(self):
        result, trades, _ = simulate(self.bars, self.inds)
        self.assertEqual(trades, [])
        self.assertEqual(result["open_position"]["stop"], 98)
        self.assertEqual(result["open_position"]["target"], 103)
        self.assertEqual(result["open_position"]["entry_time_ms"], 2 * STEP)
        self.assertAlmostEqual(result["final_equity_mark_to_market"], 9999.5)

    def test_two_sided_fee_accounting_and_target_exit(self):
        bars = self.bars + [bar(2, 100, 104, 99, 102)]
        result, trades, _ = simulate(bars, self.inds + [Indicator(97, 98, 60)])
        self.assertEqual(result["closed_trades"], 1)
        self.assertEqual(trades[0]["exit_fill"], 103)
        self.assertAlmostEqual(trades[0]["net_pnl"], 30 - .5 - .515)
        self.assertAlmostEqual(result["final_equity_mark_to_market"], 10028.985)

    def test_short_stop_above_entry_and_target_below(self):
        bars = [bar(0, 101, 101.5, 100.5, 101), bar(1, 101, 101.5, 99.5, 100),
                bar(2, 100, 101, 96, 98)]
        result, trades, _ = simulate(bars, [Indicator(102, 103, 40), Indicator(103, 102, 40), Indicator(103, 102, 40)])
        self.assertEqual(trades[0]["stop"], 102)
        self.assertEqual(trades[0]["target"], 97)
        self.assertAlmostEqual(trades[0]["net_pnl"], 30 - .5 - .485)
        self.assertEqual(result["winning_trades"], 1)

    def test_wick_touch_and_out_of_range_rsi_rejected(self):
        touching = self.bars[:1] + [replace(self.bars[1], low=98)]
        self.assertIsNone(simulate(touching, self.inds)[0]["open_position"])
        self.assertIsNone(simulate(self.bars, self.inds[:1] + [Indicator(97, 98, 71)])[0]["open_position"])

    def test_method_two_waits_for_later_key(self):
        bars = [bar(0, 99, 101, 98.5, 100), bar(1, 98, 99, 95, 96),
                bar(2, 99, 101, 98.5, 100)]
        result, _, _ = simulate(bars, [Indicator(97, 98, 60)] * 3, cfg(method="pullback"))
        self.assertEqual(result["open_position"]["method"], "L2")
        self.assertEqual(result["open_position"]["entry_time_ms"], 3 * STEP)

    def test_exit_candle_cannot_reverse_or_preserve_new_cross(self):
        bars = self.bars + [bar(2, 102, 104, 100, 101), bar(3, 102, 104, 100, 101)]
        result, trades, _ = simulate(bars, self.inds + [Indicator(106, 105, 40)] * 2, cfg(method="cross"))
        self.assertEqual(len(trades), 1)
        self.assertIsNone(result["open_position"])

    def test_prewindow_setup_is_not_carried_into_entry_window(self):
        bars = self.bars + [bar(2, 99, 102, 98.5, 100)]
        result, trades, _ = simulate(bars, self.inds + [Indicator(97, 98, 60)],
                                     replace(cfg(method="cross"), start_ms=3 * STEP))
        self.assertEqual(trades, [])
        self.assertIsNone(result["open_position"])

    def test_close_time_end_boundary_is_inclusive_like_pine(self):
        result, _, _ = simulate(self.bars, self.inds, replace(cfg(), end_ms=2 * STEP))
        self.assertIsNotNone(result["open_position"])

    def test_stop_remains_fixed_and_stop_slippage_is_adverse(self):
        bars = self.bars + [bar(2, 100, 102, 97, 99)]
        result, trades, _ = simulate(bars, self.inds + [Indicator(90, 91, 60)], cfg(slippage_ticks=1))
        self.assertEqual(trades[0]["stop"], 98)
        self.assertEqual(trades[0]["entry_fill"], 100.01)
        self.assertEqual(trades[0]["exit_fill"], 97.99)
        self.assertEqual(result["closed_trades"], 1)

    def test_quantity_rejection_clears_submitted_setup(self):
        bars = self.bars + [bar(2, 1, 2.1, .99, 2)]
        # First signal is too small for quantity step; second has no new cross.
        indicators = self.inds + [Indicator(.8, .9, 60)]
        result, _, _ = simulate(bars, indicators, cfg(initial_capital=10, qty_step=1, method="cross"))
        self.assertEqual(result["rejected_signals"], {"invalid_fill_or_quantity": 1})
        self.assertIsNone(result["open_position"])

    def test_target_hit_can_be_net_losing_after_fees(self):
        bars = [bar(0, 99, 100, 98, 99), bar(1, 99.995, 100.01, 99.995, 100),
                bar(2, 100, 100.03, 99.995, 100.02)]
        indicators = [Indicator(99, 98, 60), Indicator(99.98, 99.99, 60), Indicator(99.98, 99.99, 60)]
        result, trades, _ = simulate(bars, indicators)
        self.assertEqual(trades[0]["reason"], "target")
        self.assertLess(trades[0]["net_pnl"], 0)
        self.assertEqual(result["win_rate_percent"], 0)

    def test_audit_records_cross_trigger_and_signal_bar_without_changing_trades(self):
        bars = self.bars + [bar(2, 100, 104, 99, 102)]
        indicators = self.inds + [Indicator(97, 98, 60)]
        with patch("backtest.indicator_series", return_value=iter(indicators)):
            summary, trades, curve = run_backtest(bars, cfg(), capture_audit=True)
        audit = trades[0].pop("_audit")
        self.assertEqual(audit["trigger_bar_time"], STEP // 1000)
        self.assertEqual(audit["entry_bar_time"], STEP // 1000)
        self.assertEqual(audit["key"]["rsi"], 60)
        self.assertTrue(all(c["pass"] for c in audit["checks"]))
        plain_summary, plain_trades, plain_curve = simulate(bars, indicators)
        self.assertEqual(trades, plain_trades)
        self.assertEqual(summary, plain_summary)
        self.assertEqual(curve, plain_curve)

    def test_audit_keeps_earlier_pullback_trigger(self):
        bars = [bar(0, 98, 99, 95, 96), bar(1, 98, 99, 95, 96),
                bar(2, 99, 101, 98.5, 100)]
        indicators = [Indicator(97, 98, 60)] * 3
        with patch("backtest.indicator_series", return_value=iter(indicators)):
            result, _, _ = run_backtest(bars, cfg(method="pullback"), capture_audit=True)
        audit = result["open_position"]["audit"]
        self.assertEqual(audit["trigger_bar_time"], 0)
        self.assertEqual(audit["entry_bar_time"], 2 * STEP // 1000)
        self.assertTrue(all(c["pass"] for c in audit["checks"]))


class CsvTests(unittest.TestCase):
    def test_data_gap_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bars.csv"
            with path.open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(Candle.__dataclass_fields__)
                for b in [bar(0, 10, 10, 10, 10), bar(2, 10, 10, 10, 10)]:
                    writer.writerow(vars(b).values())
            with self.assertRaisesRegex(ValueError, "gap"):
                load_candles(path, "5m")


class FixedMarginTests(unittest.TestCase):
    def setUp(self):
        self.bars = [bar(0, 99, 99.5, 98.5, 99),
                     bar(1, 99, 104, 98.5, 100),
                     bar(2, 100, 104, 99, 102)]
        self.inds = [Indicator(98, 97, 60), Indicator(97, 98, 60),
                     Indicator(97, 98, 60)]

    def test_fixed_margin_long_uses_leverage_once_and_fees_on_notional(self):
        settings = cfg(fixed_margin=50, leverage=10)
        result, trades, _ = simulate(self.bars, self.inds, settings)
        t = trades[0]
        self.assertEqual(t["quantity"], 5)
        self.assertEqual(t["entry_notional"], 500)
        self.assertEqual(t["margin_used"], 50)
        self.assertEqual(t["leverage"], 10)
        self.assertEqual(t["gross_pnl"], 15)
        self.assertEqual(t["entry_fee"], .25)
        self.assertEqual(t["exit_fee"], .2575)
        self.assertAlmostEqual(t["net_pnl"], 14.4925)
        self.assertAlmostEqual(t["balance_after"], 10014.4925)
        self.assertAlmostEqual(result["final_equity_mark_to_market"], t["balance_after"])

    def test_fixed_margin_short_profit_and_account_balance(self):
        bars = [bar(0, 101, 101.5, 100.5, 101),
                bar(1, 101, 101.5, 99.5, 100), bar(2, 100, 101, 96, 98)]
        values = [Indicator(102, 103, 40), Indicator(103, 102, 40),
                  Indicator(103, 102, 40)]
        _, trades, _ = simulate(bars, values, cfg(fixed_margin=50, leverage=10))
        t = trades[0]
        self.assertEqual(t["quantity"], 5)
        self.assertEqual(t["gross_pnl"], 15)
        self.assertEqual(t["exit_fee"], .2425)
        self.assertAlmostEqual(t["net_pnl"], 14.5075)
        self.assertAlmostEqual(t["balance_after"], 10014.5075)

    def test_fixed_margin_does_not_compound_after_a_win(self):
        # The account grows after the first exit; the second trade is still 500.
        bars = self.bars + [bar(3, 99, 99.5, 98.5, 99),
                            bar(4, 99, 104, 98.5, 100),
                            bar(5, 100, 104, 99, 102)]
        values = self.inds + [Indicator(98, 97, 60), Indicator(97, 98, 60),
                              Indicator(97, 98, 60)]
        _, trades, _ = simulate(bars, values, cfg(fixed_margin=50, leverage=10))
        self.assertEqual(len(trades), 2)
        self.assertEqual([t["entry_notional"] for t in trades], [500, 500])
        self.assertAlmostEqual(trades[1]["balance_after"], 10028.985)

    def test_fixed_margin_size_accounts_for_entry_slippage_and_step(self):
        result, _, _ = simulate(self.bars[:2], self.inds[:2],
                                 cfg(fixed_margin=50, leverage=10, slippage_ticks=1))
        p = result["open_position"]
        self.assertEqual(p["entry"], 100.01)
        self.assertEqual(p["quantity"], 4.999)
        self.assertLessEqual(p["entry_notional"], 500)
        self.assertLessEqual(p["margin_used"], 50)
        self.assertIsNone(p["balance_after"])
        self.assertAlmostEqual(result["final_equity_mark_to_market"],
                               10000 - p["entry_fee"] + p["unrealized_pnl"])

    def test_margin_needs_fee_headroom_but_not_full_notional_in_cash(self):
        result, trades, _ = simulate(self.bars[:2], self.inds[:2],
                                     cfg(initial_capital=50.24, fixed_margin=50, leverage=10))
        self.assertEqual(trades, [])
        self.assertEqual(result["rejected_signals"], {"insufficient_margin_and_fee": 1})
        self.assertIsNone(result["open_position"])
        result, _, _ = simulate(self.bars[:2], self.inds[:2],
                                cfg(initial_capital=50.25, fixed_margin=50, leverage=10))
        self.assertEqual(result["open_position"]["entry_notional"], 500)
        self.assertEqual(result["final_equity_mark_to_market"], 50)

    def test_invalid_margin_or_leverage_rejected(self):
        for kwargs in [dict(fixed_margin=0), dict(fixed_margin=float("nan")),
                       dict(fixed_margin=50, leverage=.5), dict(leverage=10)]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    cfg(**kwargs).validate()


if __name__ == "__main__":
    unittest.main()
