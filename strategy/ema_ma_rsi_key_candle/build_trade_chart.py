#!/usr/bin/env python3
"""Re-run the strategy with signal provenance and build an embedded review chart."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backtest import (Config, indicator_series, interval_ms, load_candles,
                      round_tick, run_backtest, target_for_reference, utc_ms,
                      write_outputs)


def make_payload(candles, cfg, summary, trades, display_start, display_end):
    indicators = list(indicator_series(candles, cfg))
    step = interval_ms(cfg.interval)
    # Extra context is visible when a trade is focused near the first boundary.
    chart_bars = [
        {"time": b.open_time_ms // 1000, "open": b.open, "high": b.high,
         "low": b.low, "close": b.close, "ema": round(v.ema, 8),
         "sma": round(v.sma, 8) if v.sma is not None else None,
         "rsi": round(v.rsi, 8) if v.rsi is not None else None}
        for b, v in zip(candles, indicators)
        if cfg.start_ms - step * 72 <= b.open_time_ms < cfg.end_ms
    ]
    result = []
    records = list(trades)
    if summary["open_position"]:
        p = summary["open_position"]
        records.append({
            "direction": "long" if p["side"] == 1 else "short",
            "method": p["method"], "entry_time_utc": p["entry_time_utc"],
            "entry_reference": p["reference"], "entry_fill": p["entry"],
            "stop": p["stop"], "target": p["target"], "quantity": p["quantity"],
            "entry_notional": p["entry_notional"], "margin_used": p["margin_used"],
            "leverage": p["leverage"], "balance_after": None,
            "net_pnl": None, "gross_pnl": None, "entry_fee": p["entry_fee"],
            "exit_fee": 0, "both_levels_touched": False, "reason": "open",
            "_audit": p["audit"],
        })
    for number, record in enumerate(records, 1):
        item = {key: record.get(key) for key in ["direction", "method", "entry_reference",
                "entry_fill", "stop", "target", "quantity", "net_pnl", "gross_pnl",
                "both_levels_touched", "entry_notional", "margin_used", "leverage", "balance_after"]}
        item.update(record["_audit"])
        item["checks"] = list(item["checks"])
        closed = record["reason"] != "open"
        item.update({
            "id": number, "status": "closed" if closed else "open",
            "entry_time": utc_ms(record["entry_time_utc"]) // 1000,
            "exit_bar_time": utc_ms(record["exit_bar_open_utc"]) // 1000 if closed else None,
            "exit_bar_end_time": utc_ms(record["exit_bar_close_utc"]) // 1000 if closed else None,
            "exit_time": utc_ms(record["exit_exact_time_utc"]) // 1000 if closed and record.get("exit_exact_time_utc") else None,
            "exit_fill": record.get("exit_fill"),
            "fees": record["entry_fee"] + record["exit_fee"],
            "exit_reason": record["reason"],
        })
        side = 1 if record["direction"] == "long" else -1
        key = item["key"]
        reference, stop, target = record["entry_reference"], record["stop"], record["target"]
        item["checks"] += [
            {"label": "收盘参考价入场", "value": f"参考 {reference:.2f}；关键 K 收 {key['close']:.2f}",
             "pass": reference == key["close"]},
            {"label": "固定橙线止损", "value": f"SMA {key['sma']:.5f} → {stop:.2f}",
             "pass": stop == round_tick(key["sma"], cfg.tick_size)},
            {"label": f"固定 {cfg.reward_risk:g}R 目标", "value": f"入场 {reference:.2f}；止损 {stop:.2f}；目标 {target:.2f}",
             "pass": target == target_for_reference(reference, stop, cfg.reward_risk, cfg.tick_size)
                      and side * (target - reference) > 0},
        ]
        result.append(item)
    return {
        "meta": {
            "symbol": "ETHUSDT 永续", "interval": cfg.interval, "timezone": "Asia/Shanghai",
            "start_label": display_start, "end_label": display_end,
            "start_time": cfg.start_ms // 1000, "end_time": cfg.end_ms // 1000,
            "fee_percent": cfg.fee_percent, "slippage_ticks": cfg.slippage_ticks,
            "initial_capital": cfg.initial_capital, "fixed_margin": cfg.fixed_margin,
            "leverage": cfg.leverage, "position_percent": cfg.position_percent,
            "final_equity": summary["final_equity_mark_to_market"],
            "total_fees": summary["total_fees_paid"],
            "closed_trades": summary["closed_trades"], "win_rate_percent": summary["win_rate_percent"],
            "net_pnl": summary["closed_net_pnl"], "intrabar": cfg.intrabar,
            "data_sha256": summary["data_sha256"],
            "source_description": "币安官方 USD-M ETHUSDT K 线；本地独立回测",
            "entry_time_note": "时间轴为 K 线开盘；关键 K 收盘后入场，边界时刻含首尾。",
        }, "candles": chart_bars, "trades": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--start", default="2026-11-15T00:00:00+08:00")
    parser.add_argument("--end", default="2026-11-18T00:00:00+08:00")
    parser.add_argument("--initial-capital", type=float, default=10000)
    parser.add_argument("--fixed-margin", type=float, default=None)
    parser.add_argument("--leverage", type=float, default=1)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--fragment", required=True, type=Path)
    parser.add_argument("--template", type=Path, default=Path(__file__).with_name("trade_chart.template.html"))
    args = parser.parse_args()
    cfg = Config(start_ms=utc_ms(args.start), end_ms=utc_ms(args.end),
                 initial_capital=args.initial_capital, fixed_margin=args.fixed_margin,
                 leverage=args.leverage)
    cfg.validate()
    all_candles = load_candles(args.csv, cfg.interval)
    # The review stops at its final close and never silently uses later bars.
    candles = [b for b in all_candles if b.time_close <= cfg.end_ms]
    if not candles or candles[-1].time_close != cfg.end_ms or candles[0].time_close >= cfg.start_ms:
        parser.error("CSV must cover the full requested window and provide indicator warmup")
    summary, trades, curve = run_backtest(candles, cfg, capture_audit=True)
    summary["data_file"] = str(args.csv.resolve())
    summary["data_sha256"] = hashlib.sha256(args.csv.read_bytes()).hexdigest()
    metadata = Path(str(args.csv) + ".metadata.json")
    if metadata.exists():
        summary["data_source_metadata"] = json.loads(metadata.read_text())
        if summary["data_source_metadata"]["output_sha256"] != summary["data_sha256"]:
            raise ValueError("CSV hash differs from source metadata")
    display_zone = timezone(timedelta(hours=8))
    label = lambda timestamp: datetime.fromtimestamp(timestamp / 1000, display_zone).strftime("%Y-%m-%d %H:%M")
    payload = make_payload(candles, cfg, summary, trades, label(cfg.start_ms), label(cfg.end_ms))
    if not all(c["pass"] for t in payload["trades"] for c in t["checks"]):
        raise ValueError("at least one captured signal does not satisfy its checks")
    write_outputs(args.output_dir, summary, trades, curve)
    (args.output_dir / "trade_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    template = args.template.read_text(encoding="utf-8")
    if template.count("__TRADE_DATA_JSON__") != 1:
        raise ValueError("chart template must contain exactly one data placeholder")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    fragment = template.replace("__TRADE_DATA_JSON__", data)
    # Bundle the pinned chart library so viewing the chart needs no CDN access.
    library = Path(__file__).with_name("chart_assets") / "lightweight-charts-4.2.3.js"
    dependency = '<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>'
    if dependency not in fragment:
        raise ValueError("expected pinned chart library tag is missing")
    fragment = fragment.replace(dependency, "<script>\n" + library.read_text(encoding="utf-8").replace("</script", "<\\/script") + "\n</script>")
    if len(fragment.encode("utf-8")) >= 1_000_000:
        raise ValueError("inline review chart exceeds 1MB")
    args.fragment.parent.mkdir(parents=True, exist_ok=True)
    args.fragment.write_text(fragment, encoding="utf-8")
    print(json.dumps({"trades": len(payload["trades"]), "closed": summary["closed_trades"],
                      "win_rate": summary["win_rate_percent"], "net_pnl": summary["closed_net_pnl"],
                      "candles": len(payload["candles"]), "fragment": str(args.fragment)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
