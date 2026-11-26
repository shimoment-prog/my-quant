"""Regression against the audited saved multi-coin replay and CLI boundaries.

Default: inexpensive interface/boundary checks. Add --reference-root PATH to
replay all 320 saved profiles, including every trade, Open state and equity row.
This validates extraction from the previously independently audited engine; it
is not a second independent numerical implementation.
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import backtest as engine
import run_backtest as strategy

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def basic():
    base = dict(start_ms=200 * strategy.STEP_MS, end_ms=202 * strategy.STEP_MS,
                tick_size=.01, qty_step=.001, min_qty=.001, min_notional=20)
    assert strategy.settings(**base, exit_model="rr15", prior_bars=3).cross_direction_bars == 4
    assert strategy.settings(**base, exit_model="ema_slow", prior_bars=10).cross_direction_bars == 11
    for mode in strategy.EXITS:
        cfg = strategy.settings(**base, exit_model=mode, prior_bars=3)
        assert cfg.ema_length == cfg.ma_length == 10 and cfg.rsi_length == 14
        assert cfg.entry_rules == "directional_cross" and cfg.method == "cross"
        assert not cfg.require_key_direction and cfg.momentum_activation_required
        assert cfg.ema_slowdown_ratio == .5 and cfg.trail_activation_r == 1.5
        assert cfg.fixed_margin == 200 and cfg.leverage == 10
    assert strategy.timestamp("2021-11-23T00:00:00+08:00") == 1637596800000
    for value in ("2021-11-23", "2021-11-23T00:01:00+08:00"):
        try:
            strategy.timestamp(value)
        except ValueError:
            pass
        else:
            raise AssertionError("ambiguous/unaligned timestamp accepted")
    for mode, count in (("ema_close", 3), ("rr20", 3), ("rr15", 2), ("rr15", 11)):
        try:
            strategy.settings(**base, exit_model=mode, prior_bars=count)
        except ValueError:
            pass
        else:
            raise AssertionError("removed profile accepted")
    help_run = subprocess.run([sys.executable, "-B", str(HERE / "run_backtest.py"), "--help"],
                              capture_output=True, text=True, check=True)
    assert all(option in help_run.stdout for option in ("--tick-size", "--qty-step", "--min-qty", "--min-notional"))
    assert not any(option in help_run.stdout for option in ("--method", "--reward-risk", "--entry-rules", "--ema-length"))
    print("PASS current-rule factory, required contract filters and restricted CLI")


def regression(root):
    root = root.resolve()
    assets = json.loads((root / "universe/selection.json").read_text())["assets"]
    paths = closed = opens = equity_points = 0
    for asset in assets:
        coin = root / "coins" / asset["symbol"]
        request = json.loads((coin / "request.json").read_text())
        settings = request["config"]
        csv_path = coin / request["source_csv"]
        bars = strategy.prepared_bars(csv_path, settings["start_ms"], settings["end_ms"])
        if asset["symbol"] == "HYPEUSDT":
            assert sum(b.time_close <= settings["start_ms"] for b in bars) == 200
        for mode in strategy.EXITS:
            for prior in range(3, 11):
                run = coin / f"research/runs/{mode}/prior{prior}"
                saved = json.loads((run / "summary.json").read_text())
                cfg = strategy.settings(
                    start_ms=settings["start_ms"], end_ms=settings["end_ms"],
                    tick_size=settings["tick_size"], qty_step=settings["qty_step"],
                    min_qty=settings["min_qty"], min_notional=settings["min_notional"],
                    exit_model=mode, prior_bars=prior)
                assert asdict(cfg) == saved["config"], (asset["symbol"], mode, prior, "config")
                summary, trades, curve = engine.run_backtest(bars, cfg, capture_audit=True)
                expected = json.loads((run / "trades-with-audit.json").read_text())
                assert trades == expected, (asset["symbol"], mode, prior, "trades")
                assert summary["open_position"] == saved["open_position"], (asset["symbol"], mode, prior, "Open")
                assert summary["final_equity_mark_to_market"] == saved["final_equity_mark_to_market"]
                with (run / "equity.csv").open() as stream:
                    reader = csv.DictReader(stream)
                    points = list(reader)
                assert len(points) == len(curve)
                for old, new in zip(points, curve):
                    assert old["time_utc"] == new["time_utc"]
                    for field in ("equity", "cash", "unrealized_pnl", "drawdown_percent"):
                        assert float(old[field]) == new[field], (asset["symbol"], mode, prior, field)
                paths += 1; closed += len(trades); opens += summary["open_position"] is not None
                equity_points += len(curve)
        print(f"PASS {asset['symbol']} all 32 trade/Open/equity paths", flush=True)
    assert (paths, closed, opens, equity_points) == (320, 9194, 4, 3253152)
    # An earlier end inside a larger supplied CSV must crop future candles.
    coin = root / "coins" / "ETHUSDT"
    request = json.loads((coin / "request.json").read_text())
    cfg = request["config"]
    earlier_end = cfg["end_ms"] - strategy.STEP_MS
    cropped = strategy.prepared_bars(coin / request["source_csv"], cfg["start_ms"], earlier_end)
    assert cropped[-1].time_close == earlier_end
    for mode in strategy.EXITS:
        actual_cfg = strategy.settings(
            start_ms=cfg["start_ms"], end_ms=earlier_end, tick_size=cfg["tick_size"],
            qty_step=cfg["qty_step"], min_qty=cfg["min_qty"], min_notional=cfg["min_notional"],
            exit_model=mode, prior_bars=3)
        summary, trades, curve = engine.run_backtest(cropped, actual_cfg, capture_audit=True)
        assert curve[-1]["time_utc"] == engine.utc_text(earlier_end)
        assert all(engine.utc_ms(t["exit_bar_close_utc"]) <= earlier_end for t in trades)
    print(json.dumps({"pass": True, "profiles": paths, "closed": closed, "open": opens,
                      "equity_points": equity_points, "end_crop_checked": True,
                      "core_sha256": hashlib.sha256((HERE / "backtest.py").read_bytes()).hexdigest()}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path)
    args = parser.parse_args()
    basic()
    if args.reference_root:
        regression(args.reference_root)
