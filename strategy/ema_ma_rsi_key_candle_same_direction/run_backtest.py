#!/usr/bin/env python3
"""Replay the saved same-direction strategy; default to all 32 profiles.

Uses local Binance-style OHLCV CSV only. There is no trading/account API.
Timestamp boundaries must include a UTC offset and fall on a four-hour close.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import backtest as engine

STRATEGY_ID = "ema_ma_rsi_key_candle_same_direction"
STRATEGY_VERSION = "1.0.0"
SOURCE_ENGINE_SHA256 = "e1118faa696e0bb18db1def942b9b6d622817385cd569a5aee1e3d290b12c3ae"
STEP_MS = 14_400_000
WARMUP_BARS = 200
EXITS = {
    "rr15": {"label": "原版1.5R", "mode": "fixed"},
    "trail_ema": {"label": "1.5R后EMA追踪", "mode": "ema_trail"},
    "ema_slow": {"label": "EMA明显变缓收盘平仓", "mode": "ema_slow"},
    "ema_turn": {"label": "EMA转向收盘平仓", "mode": "ema_turn"},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("start/end must include a UTC offset, for example 2021-11-23T00:00:00+08:00")
    stamp = int(parsed.timestamp() * 1000)
    if stamp % STEP_MS:
        raise ValueError("start/end must align to a Binance four-hour boundary")
    return stamp


def settings(*, start_ms, end_ms, tick_size, qty_step, min_qty, min_notional,
             exit_model, prior_bars, initial_capital=10000, fixed_margin=200,
             leverage=10, fee_percent=0.05, slippage_ticks=0):
    """Create a profile without exposing historical/removed entry modes."""
    if exit_model not in EXITS:
        raise ValueError("unsupported exit model")
    if type(prior_bars) is not int or prior_bars not in range(3, 11):
        raise ValueError("prior_bars must be an integer from 3 through 10")
    if min_qty <= 0 or min_notional <= 0:
        raise ValueError("Binance minimum quantity and notional snapshots must be positive")
    cfg = engine.Config(
        start_ms=start_ms, end_ms=end_ms, interval="4h",
        ema_length=10, ma_length=10, rsi_length=14,
        long_rsi_min=50, long_rsi_max=70, short_rsi_min=30, short_rsi_max=50,
        direction="both", method="cross", reward_risk=1.5,
        initial_capital=initial_capital, fixed_margin=fixed_margin,
        leverage=leverage, fee_percent=fee_percent, slippage_ticks=slippage_ticks,
        tick_size=tick_size, qty_step=qty_step, min_qty=min_qty,
        min_notional=min_notional, intrabar="stop-first",
        entry_rules="directional_cross", cross_direction_bars=prior_bars + 1,
        require_key_direction=False, exit_mode=EXITS[exit_model]["mode"],
        trail_activation_r=1.5, ema_slowdown_ratio=0.5,
        momentum_activation_required=True)
    cfg.validate()
    return cfg


def prepared_bars(path, start_ms, end_ms):
    if start_ms >= end_ms:
        raise ValueError("start must precede end")
    candles = engine.load_candles(path, "4h")
    if candles[-1].time_close < end_ms:
        raise ValueError("CSV must cover the requested end boundary")
    # The core accepts all supplied bars. Crop here to prevent future-bar exits
    # or equity updates after the declared experiment end.
    candles = [bar for bar in candles if bar.time_close <= end_ms]
    if not candles or candles[-1].time_close != end_ms:
        raise ValueError("CSV does not contain the requested end close")
    count = sum(bar.time_close <= start_ms for bar in candles)
    if count < WARMUP_BARS:
        raise ValueError(f"need at least {WARMUP_BARS} completed warmup candles at/before start; found {count}")
    return candles


def metrics(summary, trades, symbol, exit_model, prior_bars):
    return {
        "strategy_id": STRATEGY_ID, "strategy_definition_version": STRATEGY_VERSION,
        "symbol": symbol, "exit_model": exit_model,
        "exit_label": EXITS[exit_model]["label"], "prior_bars": prior_bars,
        "directional_changes_checked": prior_bars + 1,
        "closed": summary["closed_trades"], "wins": summary["winning_trades"],
        "losses": summary["losing_trades"], "flats": summary["breakeven_trades"],
        "win_rate": summary["win_rate_percent"],
        "closed_net": summary["closed_net_pnl"],
        "fees": summary["total_fees_paid"],
        "net_mtm": summary["final_equity_mark_to_market"] - summary["config"]["initial_capital"],
        "final_equity": summary["final_equity_mark_to_market"],
        "max_drawdown_percent": summary["max_drawdown_percent_at_bar_close"],
        "profit_factor_net": summary["profit_factor_net"],
        "open": summary["open_position"] is not None,
        "source_engine_sha256": SOURCE_ENGINE_SHA256,
    }


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--symbol", required=True, help="Binance USDT perpetual symbol, e.g. ETHUSDT")
    p.add_argument("--start", required=True, help="inclusive entry-close boundary; explicit UTC offset")
    p.add_argument("--end", required=True, help="inclusive entry-close boundary; data is cropped at this close")
    p.add_argument("--tick-size", type=float, required=True)
    p.add_argument("--qty-step", type=float, required=True)
    p.add_argument("--min-qty", type=float, required=True)
    p.add_argument("--min-notional", type=float, required=True)
    p.add_argument("--output", type=Path, required=True, help="new or empty output directory")
    p.add_argument("--exit-model", choices=list(EXITS), nargs="+", default=list(EXITS))
    p.add_argument("--prior-bars", type=int, choices=range(3, 11), nargs="+", default=list(range(3, 11)))
    p.add_argument("--initial-capital", type=float, default=10000)
    p.add_argument("--fixed-margin", type=float, default=200)
    p.add_argument("--leverage", type=float, default=10)
    p.add_argument("--fee-percent", type=float, default=0.05)
    p.add_argument("--slippage-ticks", type=int, default=0)
    return p


def main(argv=None):
    p = parser(); args = p.parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Z0-9]+USDT", args.symbol):
            raise ValueError("symbol must be an uppercase Binance USDT contract symbol")
        start_ms, end_ms = timestamp(args.start), timestamp(args.end)
        modes, prior_counts = list(dict.fromkeys(args.exit_model)), list(dict.fromkeys(args.prior_bars))
        cfg_args = {name: getattr(args, name) for name in (
            "tick_size", "qty_step", "min_qty", "min_notional", "initial_capital",
            "fixed_margin", "leverage", "fee_percent", "slippage_ticks")}
        # Validate all configuration inputs before creating any result files.
        for mode in modes:
            for prior in prior_counts:
                settings(start_ms=start_ms, end_ms=end_ms, exit_model=mode, prior_bars=prior, **cfg_args)
        candles = prepared_bars(args.csv, start_ms, end_ms)
        if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
            raise ValueError("output must be a new or empty directory")
        args.output.mkdir(parents=True, exist_ok=True)
        provenance = {
            "strategy_id": STRATEGY_ID, "strategy_definition_version": STRATEGY_VERSION,
            "symbol": args.symbol, "csv": str(args.csv.resolve()), "csv_sha256": sha(args.csv),
            "source_engine_sha256": SOURCE_ENGINE_SHA256,
            "core_sha256": sha(Path(engine.__file__)), "runner_sha256": sha(__file__),
            "start_ms": start_ms, "end_ms": end_ms, "exit_models": modes,
            "prior_bars": prior_counts, "account_and_filters": cfg_args,
            "completed_warmup_bars_at_or_before_start": sum(b.time_close <= start_ms for b in candles),
            "effective_data_last_close_utc": engine.utc_text(candles[-1].time_close),
            "timestamp_convention": "entry scheduled close inclusive at both bounds; supplied future candles excluded",
            "accounts": "Every exit/prior profile is independently funded; no combined portfolio.",
        }
        (args.output / "request.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
        comparisons = []
        for mode in modes:
            for prior in prior_counts:
                cfg = settings(start_ms=start_ms, end_ms=end_ms, exit_model=mode, prior_bars=prior, **cfg_args)
                summary, trades, curve = engine.run_backtest(candles, cfg, capture_audit=True)
                summary.update(strategy_id=STRATEGY_ID, strategy_definition_version=STRATEGY_VERSION,
                               symbol=args.symbol, source_engine_sha256=SOURCE_ENGINE_SHA256,
                               registered_exit_model=mode, prior_direction_bars=prior)
                directory = args.output / mode / f"prior{prior}"
                engine.write_outputs(directory, summary, trades, curve)
                (directory / "trades-with-audit.json").write_text(json.dumps(trades, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
                (directory / "open-position.json").write_text(json.dumps(summary["open_position"], ensure_ascii=False, indent=2, allow_nan=False) + "\n")
                comparisons.append(metrics(summary, trades, args.symbol, mode, prior))
        (args.output / "comparison.json").write_text(json.dumps(comparisons, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        with (args.output / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(comparisons[0])); w.writeheader(); w.writerows(comparisons)
        print(json.dumps({"strategy_id": STRATEGY_ID, "profiles": len(comparisons),
                          "closed_records": sum(x["closed"] for x in comparisons),
                          "open_profiles": sum(x["open"] for x in comparisons),
                          "output": str(args.output.resolve())}, ensure_ascii=False))
    except (ValueError, OSError) as error:
        p.error(str(error))


if __name__ == "__main__":
    main()
