#!/usr/bin/env python3
"""Backtest the companion Pine rules using public Binance USD-M OHLCV data.

This is an independent bar simulator, not the TradingView broker emulator.
Only Python's standard library is required. No account or trading API is used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Candle:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time_ms: int

    @property
    def time_close(self):
        # Binance's last millisecond versus Pine's scheduled bar boundary.
        return self.close_time_ms + 1


@dataclass(frozen=True)
class Indicator:
    ema: float
    sma: Optional[float]
    rsi: Optional[float]


@dataclass(frozen=True)
class Config:
    start_ms: int
    end_ms: int
    interval: str = "5m"
    ema_length: int = 10
    ma_length: int = 10
    rsi_length: int = 14
    long_rsi_min: float = 50
    long_rsi_max: float = 70
    short_rsi_min: float = 30
    short_rsi_max: float = 50
    direction: str = "both"
    method: str = "both"
    reward_risk: float = 1.5
    initial_capital: float = 10000
    position_percent: float = 10
    fixed_margin: Optional[float] = None
    leverage: float = 1
    fee_percent: float = 0.05
    slippage_ticks: int = 0
    tick_size: float = 0.01
    qty_step: float = 0.001
    intrabar: str = "stop-first"

    def validate(self):
        if self.start_ms >= self.end_ms:
            raise ValueError("start must precede end")
        if min(self.ema_length, self.ma_length, self.rsi_length) < 1:
            raise ValueError("indicator lengths must be positive")
        for lo, hi in [(self.long_rsi_min, self.long_rsi_max),
                       (self.short_rsi_min, self.short_rsi_max)]:
            if not (0 <= lo <= hi <= 100):
                raise ValueError("invalid RSI bounds")
        for value in [self.reward_risk, self.initial_capital, self.tick_size,
                      self.qty_step, self.position_percent]:
            if not math.isfinite(value) or value <= 0:
                raise ValueError("capital, size, tick, quantity step and R must be positive")
        if not math.isfinite(self.leverage) or self.leverage < 1:
            raise ValueError("leverage must be finite and at least 1")
        if self.fixed_margin is not None:
            if not math.isfinite(self.fixed_margin) or self.fixed_margin <= 0:
                raise ValueError("fixed_margin must be finite and positive")
            if not math.isfinite(self.fixed_margin * self.leverage):
                raise ValueError("fixed margin times leverage must be finite")
        elif self.leverage != 1:
            raise ValueError("leverage requires fixed_margin sizing")
        elif self.position_percent > 100:
            raise ValueError("equity-percent sizing requires position_percent <= 100")
        if not math.isfinite(self.fee_percent) or self.fee_percent < 0:
            raise ValueError("fee_percent must be nonnegative")
        if self.slippage_ticks < 0:
            raise ValueError("slippage_ticks must be nonnegative")
        if self.direction not in {"both", "long", "short"}:
            raise ValueError("invalid direction")
        if self.method not in {"both", "cross", "pullback"}:
            raise ValueError("invalid method")
        if self.intrabar not in {"stop-first", "tv-path"}:
            raise ValueError("invalid intrabar policy")
        interval_ms(self.interval)


@dataclass
class Position:
    side: int
    method: str
    entry_bar: int
    entry_time_ms: int
    reference: float
    entry: float
    stop: float
    target: float
    quantity: float
    entry_fee: float
    audit: Optional[dict] = None


def utc_ms(value):
    """Dates and timestamps without a UTC offset are explicitly interpreted as UTC."""
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return int(result.timestamp() * 1000)


def utc_text(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def interval_ms(value):
    if len(value) < 2 or not value[:-1].isdigit() or value[-1] not in "mhd":
        raise ValueError("use a fixed interval such as 1m, 5m, 1h or 1d")
    result = int(value[:-1]) * {"m": 60000, "h": 3600000, "d": 86400000}[value[-1]]
    if result <= 0:
        raise ValueError("interval must be positive")
    return result


def load_candles(path, interval):
    step = interval_ms(interval)
    result = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = set(Candle.__dataclass_fields__)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("CSV must contain: " + ",".join(Candle.__dataclass_fields__))
        for line_number, row in enumerate(reader, 2):
            try:
                bar = Candle(int(row["open_time_ms"]), float(row["open"]),
                             float(row["high"]), float(row["low"]),
                             float(row["close"]), float(row["volume"]),
                             int(row["close_time_ms"]))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"invalid CSV row {line_number}") from exc
            values = [bar.open, bar.high, bar.low, bar.close, bar.volume]
            if not all(math.isfinite(x) for x in values):
                raise ValueError(f"nonfinite OHLCV at CSV row {line_number}")
            if not (0 < bar.low <= min(bar.open, bar.close) <=
                    max(bar.open, bar.close) <= bar.high) or bar.volume < 0:
                raise ValueError(f"invalid OHLCV at CSV row {line_number}")
            if bar.time_close != bar.open_time_ms + step:
                raise ValueError(f"wrong candle duration at CSV row {line_number}")
            if result and bar.open_time_ms != result[-1].open_time_ms + step:
                raise ValueError(f"gap, duplicate or unsorted CSV at row {line_number}")
            result.append(bar)
    if not result:
        raise ValueError("empty candle CSV")
    return result


def indicator_series(candles, cfg):
    closes = deque(maxlen=cfg.ma_length)
    gains, losses = [], []
    ema = None
    up = down = None
    previous = None
    alpha = 2 / (cfg.ema_length + 1)
    for bar in candles:
        ema = bar.close if ema is None else alpha * bar.close + (1 - alpha) * ema
        # Decimal price averaging avoids a binary sum drifting just below a
        # half-tick before the signal's SMA is rounded into a stop order.
        closes.append(Decimal(str(bar.close)))
        sma = float(sum(closes) / cfg.ma_length) if len(closes) == cfg.ma_length else None
        if previous is not None:
            gain, loss = max(bar.close - previous, 0), max(previous - bar.close, 0)
            if up is None:
                gains.append(gain)
                losses.append(loss)
                if len(gains) == cfg.rsi_length:
                    up = sum(gains) / cfg.rsi_length
                    down = sum(losses) / cfg.rsi_length
            else:
                up = (up * (cfg.rsi_length - 1) + gain) / cfg.rsi_length
                down = (down * (cfg.rsi_length - 1) + loss) / cfg.rsi_length
        rsi = None
        if up is not None:
            # Explicit zero guards follow the common TradingView RSI formulation.
            rsi = 100.0 if down == 0 else 0.0 if up == 0 else 100 - 100 / (1 + up / down)
        yield Indicator(ema, sma, rsi)
        previous = bar.close


def round_tick(value, tick):
    step = Decimal(str(tick))
    return float((Decimal(str(value)) / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step)


def floor_quantity(value, step):
    quantum = Decimal(str(step))
    return float((Decimal(str(value)) / quantum).quantize(Decimal("1"), rounding=ROUND_FLOOR) * quantum)


def target_for_reference(reference, stop, reward_risk, tick):
    # The same expression gives the correct target on both sides of the market.
    price, stopped = Decimal(str(reference)), Decimal(str(stop))
    return round_tick(price + Decimal(str(reward_risk)) * (price - stopped), tick)


def resolve_exit(position, bar, policy):
    """Return raw fill, reason, ambiguity. Stop slippage is applied by the caller."""
    p = position
    if p.side == 1:
        if bar.open <= p.stop:
            return bar.open, "stop_gap", False
        if bar.open >= p.target:
            return bar.open, "target_gap", False
        stop_hit, target_hit = bar.low <= p.stop, bar.high >= p.target
    else:
        if bar.open >= p.stop:
            return bar.open, "stop_gap", False
        if bar.open <= p.target:
            return bar.open, "target_gap", False
        stop_hit, target_hit = bar.high >= p.stop, bar.low <= p.target
    if not stop_hit and not target_hit:
        return None
    if stop_hit and target_hit:
        # TV-style OHLC path assumption; equal distances explicitly choose low first.
        high_first = abs(bar.high - bar.open) < abs(bar.open - bar.low)
        target_first = policy == "tv-path" and (high_first == (p.side == 1))
        return (p.target, "target_both", True) if target_first else (p.stop, "stop_both", True)
    return (p.stop, "stop", False) if stop_hit else (p.target, "target", False)


def entry_audit(candles, indicators, index, trigger_index, side, method, cfg):
    """Record the exact signal values; chart dates always refer to bar OPENS."""
    bar, ind = candles[index], indicators[index]
    trigger, trigger_ind = candles[trigger_index], indicators[trigger_index]
    previous = indicators[trigger_index - 1] if trigger_index else None
    long = side == 1
    cross = method.endswith("1")
    trend_ok = ind.sma > ind.ema if long else ind.sma < ind.ema
    candle_ok = bar.close > bar.open if long else bar.close < bar.open
    wick_ok = bar.low > max(ind.ema, ind.sma) if long else bar.high < min(ind.ema, ind.sma)
    lo, hi = (cfg.long_rsi_min, cfg.long_rsi_max) if long else (cfg.short_rsi_min, cfg.short_rsi_max)
    relation = ">" if long else "<"
    earlier_keys = 0
    for i in range(trigger_index if cross else trigger_index + 1, index):
        candidate, values = candles[i], indicators[i]
        key_ok = (candidate.close > candidate.open and candidate.low > max(values.sma, values.ema)
                  and values.sma > values.ema if long else
                  candidate.close < candidate.open and candidate.high < min(values.sma, values.ema)
                  and values.sma < values.ema)
        if not key_ok or not lo <= values.rsi <= hi:
            continue
        candidate_stop = round_tick(values.sma, cfg.tick_size)
        candidate_target = target_for_reference(candidate.close, candidate_stop, cfg.reward_risk, cfg.tick_size)
        valid_bracket = (side * (candidate.close - candidate_stop) + cfg.tick_size * 1e-9 >= cfg.tick_size
                         and candidate_target > 0 and side * (candidate_target - candidate.close) > 0)
        earlier_keys += bool(valid_bracket)
    checks = [
        {"label": "均线排列", "value": f"SMA {ind.sma:.5f} {relation} EMA {ind.ema:.5f}", "pass": trend_ok},
        {"label": "关键 K 阳线" if long else "关键 K 阴线",
         "value": f"收 {bar.close:.2f} {relation} 开 {bar.open:.2f}", "pass": candle_ok},
        {"label": "整根影线在两线上方" if long else "整根影线在两线下方",
         "value": (f"低 {bar.low:.2f} > 两线最高 {max(ind.ema, ind.sma):.5f}" if long else
                   f"高 {bar.high:.2f} < 两线最低 {min(ind.ema, ind.sma):.5f}"), "pass": wick_ok},
        {"label": "RSI 区间（含边界）", "value": f"{lo:g} ≤ {ind.rsi:.5f} ≤ {hi:g}", "pass": lo <= ind.rsi <= hi},
        {"label": "触发至入场时序", "value": f"触发后 {index-trigger_index} 根；{'允许触发当根' if cross else '必须晚于触发 K'}",
         "pass": index >= trigger_index if cross else index > trigger_index},
        {"label": "等待期间均线方向有效", "value": f"核对 {index-trigger_index+1} 根",
         "pass": all(v.sma is not None and (v.sma > v.ema if long else v.sma < v.ema)
                     for v in indicators[trigger_index:index+1])},
        {"label": "首根合格关键 K", "value": f"本次触发后，此前符合关键 K 且止盈止损有效的 K：{earlier_keys} 根",
         "pass": earlier_keys == 0},
    ]
    if cross:
        triggered = previous is not None and previous.sma is not None and (
            trigger_ind.sma > trigger_ind.ema and previous.sma <= previous.ema if long else
            trigger_ind.sma < trigger_ind.ema and previous.sma >= previous.ema)
        checks.append({"label": "方式一交叉触发", "value": "橙线上穿白线" if long else "橙线下穿白线", "pass": triggered})
    else:
        triggered = (trigger.close < trigger.open and trigger.close < trigger_ind.ema and trigger_ind.sma > trigger_ind.ema
                     if long else trigger.close > trigger.open and trigger.close > trigger_ind.ema and trigger_ind.sma < trigger_ind.ema)
        checks.append({"label": "方式二回踩／反弹触发", "value":
                       f"开 {trigger.open:.2f}，收 {trigger.close:.2f}，白线 {trigger_ind.ema:.5f}", "pass": triggered})
    return {
        "entry_bar_time": bar.open_time_ms // 1000,
        "trigger_bar_time": trigger.open_time_ms // 1000,
        "trigger_kind": "cross" if cross else "pullback",
        "trigger": {"open": trigger.open, "high": trigger.high, "low": trigger.low,
                    "close": trigger.close, "ema": trigger_ind.ema, "sma": trigger_ind.sma,
                    "previous_ema": previous.ema if previous else None,
                    "previous_sma": previous.sma if previous else None},
        "key": {"open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close,
                "ema": ind.ema, "sma": ind.sma, "rsi": ind.rsi},
        "checks": checks,
    }


def run_backtest(candles, cfg, capture_audit=False):
    cfg.validate()
    cash = cfg.initial_capital
    position = None
    long_armed = short_armed = False
    long_cross_bar = short_cross_bar = None
    long_pullback = short_pullback = None
    prev = None
    trades, curve = [], []
    rejected = Counter()
    peak, max_dd, max_dd_amount = cash, 0.0, 0.0
    fee_rate = cfg.fee_percent / 100
    slip = cfg.slippage_ticks * cfg.tick_size
    long_enabled = cfg.direction != "short"
    short_enabled = cfg.direction != "long"
    cross_enabled = cfg.method != "pullback"
    pullback_enabled = cfg.method != "cross"

    indicators = list(indicator_series(candles, cfg))
    for index, (bar, ind) in enumerate(zip(candles, indicators)):
        closed_this_bar = False
        # Only a position opened on an EARLIER close can use this candle's range.
        if position is not None:
            resolution = resolve_exit(position, bar, cfg.intrabar)
            if resolution is not None:
                raw_exit, reason, ambiguous = resolution
                exit_fill = raw_exit - position.side * slip if reason.startswith("stop") else raw_exit
                if exit_fill <= 0:
                    raise ValueError("slippage produces a nonpositive exit fill")
                gross = position.side * position.quantity * (exit_fill - position.entry)
                exit_fee = position.quantity * exit_fill * fee_rate
                cash += gross - exit_fee
                trades.append({
                    "direction": "long" if position.side == 1 else "short",
                    "method": position.method,
                    "entry_time_utc": utc_text(position.entry_time_ms),
                    "entry_reference": position.reference,
                    "entry_fill": position.entry,
                    "stop": position.stop,
                    "target": position.target,
                    "quantity": position.quantity,
                    "entry_notional": position.quantity * position.entry,
                    "margin_used": position.quantity * position.entry / cfg.leverage,
                    "leverage": cfg.leverage,
                    "exit_bar_open_utc": utc_text(bar.open_time_ms),
                    "exit_bar_close_utc": utc_text(bar.time_close),
                    "exit_exact_time_utc": utc_text(bar.open_time_ms) if reason.endswith("gap") else None,
                    "exit_fill": exit_fill,
                    "reason": reason,
                    "both_levels_touched": ambiguous,
                    "gross_pnl": gross,
                    "entry_fee": position.entry_fee,
                    "exit_fee": exit_fee,
                    "net_pnl": gross - position.entry_fee - exit_fee,
                    "balance_after": cash,
                    "bars_held": index - position.entry_bar,
                })
                if capture_audit:
                    trades[-1]["_audit"] = position.audit
                position = None
                closed_this_bar = True

        ready = ind.sma is not None and ind.rsi is not None
        # Match the companion Pine time_close >= start and <= end exactly.
        in_window = cfg.start_ms <= bar.time_close <= cfg.end_ms
        if not ready or not in_window or position is not None or closed_this_bar:
            long_armed = short_armed = False
            long_cross_bar = short_cross_bar = None
            long_pullback = short_pullback = None
        else:
            orange, white, rsi = ind.sma, ind.ema, ind.rsi
            long_trend, short_trend = orange > white, orange < white
            if not long_trend:
                long_armed, long_pullback = False, None
                long_cross_bar = None
            if not short_trend:
                short_armed, short_pullback = False, None
                short_cross_bar = None
            cross_up = prev is not None and prev.sma is not None and orange > white and prev.sma <= prev.ema
            cross_down = prev is not None and prev.sma is not None and orange < white and prev.sma >= prev.ema
            if long_enabled and cross_enabled and cross_up:
                long_armed = True
                long_cross_bar = index
            if short_enabled and cross_enabled and cross_down:
                short_armed = True
                short_cross_bar = index
            if (long_enabled and pullback_enabled and long_trend and bar.close < bar.open
                    and bar.close < white and long_pullback is None):
                long_pullback = index
            if (short_enabled and pullback_enabled and short_trend and bar.close > bar.open
                    and bar.close > white and short_pullback is None):
                short_pullback = index
            long_key = (bar.close > bar.open and bar.low > max(orange, white)
                        and cfg.long_rsi_min <= rsi <= cfg.long_rsi_max)
            short_key = (bar.close < bar.open and bar.high < min(orange, white)
                         and cfg.short_rsi_min <= rsi <= cfg.short_rsi_max)
            long_via_cross = cross_enabled and long_armed
            short_via_cross = cross_enabled and short_armed
            long_via_pullback = pullback_enabled and long_pullback is not None and index > long_pullback
            short_via_pullback = pullback_enabled and short_pullback is not None and index > short_pullback
            side, entry_method = 0, None
            if long_enabled and long_trend and long_key and (long_via_cross or long_via_pullback):
                side, entry_method = 1, "L1" if long_via_cross else "L2"
            elif short_enabled and short_trend and short_key and (short_via_cross or short_via_pullback):
                side, entry_method = -1, "S1" if short_via_cross else "S2"
            if side:
                stop = round_tick(orange, cfg.tick_size)
                risk = side * (bar.close - stop)
                target = target_for_reference(bar.close, stop, cfg.reward_risk, cfg.tick_size)
                if risk + cfg.tick_size * 1e-9 < cfg.tick_size or target <= 0 or side * (target - bar.close) <= 0:
                    rejected["invalid_stop_or_target"] += 1
                else:
                    fill = bar.close + side * slip
                    if cfg.fixed_margin is None:
                        # Preserve the companion Pine's original reference-price sizing.
                        quantity = floor_quantity(cash * cfg.position_percent / 100 / bar.close, cfg.qty_step)
                    else:
                        # Fixed collateral, without compounding. Leverage sets the
                        # exposure once; PnL already reflects that larger quantity.
                        quantity = (floor_quantity(cfg.fixed_margin * cfg.leverage / fill, cfg.qty_step)
                                    if fill > 0 else 0)
                    entry_fee = quantity * fill * fee_rate
                    entry_notional = quantity * fill
                    margin_used = entry_notional / cfg.leverage
                    if fill <= 0 or quantity <= 0:
                        rejected["invalid_fill_or_quantity"] += 1
                    elif margin_used + entry_fee > cash:
                        rejected["insufficient_margin_and_fee" if cfg.fixed_margin is not None
                                 else "insufficient_unlevered_capital"] += 1
                    else:
                        trigger_index = (long_cross_bar if side == 1 else short_cross_bar) if entry_method.endswith("1") else (
                            long_pullback if side == 1 else short_pullback)
                        audit = entry_audit(candles, indicators, index, trigger_index, side, entry_method, cfg) if capture_audit else None
                        position = Position(side, entry_method, index, bar.time_close,
                                            bar.close, fill, stop, target, quantity, entry_fee, audit)
                        cash -= entry_fee
                    # Pine clears setups when an order is SUBMITTED, even if
                    # the broker subsequently rejects its quantity or margin.
                    long_armed = short_armed = False
                    long_cross_bar = short_cross_bar = None
                    long_pullback = short_pullback = None

        unrealized = position.side * position.quantity * (bar.close - position.entry) if position else 0.0
        equity = cash + unrealized
        if bar.time_close >= cfg.start_ms:
            peak = max(peak, equity)
            drawdown_amount = peak - equity
            max_dd_amount = max(max_dd_amount, drawdown_amount)
            max_dd = max(max_dd, drawdown_amount / peak if peak else 0)
            curve.append({"time_utc": utc_text(bar.time_close), "equity": equity,
                          "cash": cash, "unrealized_pnl": unrealized,
                          "drawdown_percent": 100 * drawdown_amount / peak if peak else 0})
        prev = ind

    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] < 0]
    profit, loss = sum(t["net_pnl"] for t in wins), -sum(t["net_pnl"] for t in losses)
    final_equity = curve[-1]["equity"] if curve else cash
    open_position = None
    if position:
        open_position = asdict(position)
        open_position["entry_time_utc"] = utc_text(position.entry_time_ms)
        open_position["unrealized_pnl"] = position.side * position.quantity * (candles[-1].close - position.entry)
        open_position["entry_notional"] = position.quantity * position.entry
        open_position["margin_used"] = position.quantity * position.entry / cfg.leverage
        open_position["leverage"] = cfg.leverage
        open_position["balance_after"] = None
    summary = {
        "config": asdict(cfg),
        "entry_close_start_utc_inclusive": utc_text(cfg.start_ms),
        "entry_close_end_utc_inclusive": utc_text(cfg.end_ms),
        "data_first_open_utc": utc_text(candles[0].open_time_ms),
        "data_last_close_utc": utc_text(candles[-1].time_close),
        "data_bars": len(candles),
        "warmup_bars_before_entry_start": sum(b.time_close < cfg.start_ms for b in candles),
        "closed_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "breakeven_trades": len(trades) - len(wins) - len(losses),
        "win_rate_percent": 100 * len(wins) / len(trades) if trades else None,
        "profit_factor_net": profit / loss if loss else None,
        "closed_net_pnl": sum(t["net_pnl"] for t in trades),
        "total_fees_paid": sum(t["entry_fee"] + t["exit_fee"] for t in trades) + (position.entry_fee if position else 0),
        "final_equity_mark_to_market": final_equity,
        "total_return_percent_mark_to_market": 100 * (final_equity / cfg.initial_capital - 1),
        "max_drawdown_percent_at_bar_close": 100 * max_dd,
        "max_drawdown_amount_at_bar_close": max_dd_amount,
        "ambiguous_exit_bars": sum(t["both_levels_touched"] for t in trades),
        "rejected_signals": dict(rejected),
        "open_position": open_position,
        "method_counts": dict(Counter(t["method"] for t in trades)),
        "position_sizing": {
            "mode": "fixed_margin" if cfg.fixed_margin is not None else "equity_percent",
            "fixed_margin": cfg.fixed_margin,
            "leverage": cfg.leverage,
            "target_entry_notional": cfg.fixed_margin * cfg.leverage if cfg.fixed_margin is not None else None,
            "quantity_rounding": "floor_to_qty_step",
        },
        "funding_included": False,
        "liquidation_modelled": False,
        "limitations": [
            "Independent OHLC simulator; not verified for exact TradingView trade parity.",
            "Funding payments, mark-price triggers and Binance liquidation tiers are excluded.",
            "Drawdown is measured at bar closes, not intrabar equity extremes.",
            "Intrabar exit timestamps are unknown; CSV reports their enclosing candle.",
            "Final open position is marked to market, not forcibly closed or included in win rate.",
            "Tick and quantity steps are user parameters, not historical exchange-rule verification.",
            "RSI uses Wilder smoothing; on all-flat prices its explicit zero-loss guard returns 100.",
        ],
    }
    return summary, trades, curve


TRADE_COLUMNS = ["direction", "method", "entry_time_utc", "entry_reference", "entry_fill",
                 "stop", "target", "quantity", "entry_notional", "margin_used", "leverage",
                 "exit_bar_open_utc", "exit_bar_close_utc",
                 "exit_exact_time_utc", "exit_fill", "reason", "both_levels_touched",
                 "gross_pnl", "entry_fee", "exit_fee", "net_pnl", "balance_after", "bars_held"]


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(output, summary, trades, curve):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_csv(output / "trades.csv", trades, TRADE_COLUMNS)
    write_csv(output / "equity.csv", curve, ["time_utc", "equity", "cash", "unrealized_pnl", "drawdown_percent"])
    def fmt(value, digits=2):
        return "—" if value is None else f"{value:,.{digits}f}"
    cfg = summary["config"]
    sizing_text = (f"每笔目标保证金 {cfg['fixed_margin']:g} USDT，{cfg['leverage']:g} 倍杠杆，目标名义仓位 {cfg['fixed_margin'] * cfg['leverage']:g} USDT；数量按步长向下取整"
                   if cfg.get("fixed_margin") is not None else
                   f"每笔使用权益 {cfg['position_percent']:g}%，无杠杆")
    text = ["# 币安 ETHUSDT 永续历史回测", "",
            f"开仓收盘时刻：{summary['entry_close_start_utc_inclusive']} 至 {summary['entry_close_end_utc_inclusive']}，两端含，UTC。",
            f"数据：{summary['data_first_open_utc']} 至 {summary['data_last_close_utc']}；{cfg['interval']}，共 {summary['data_bars']:,} 根，开仓前预热 {summary['warmup_bars_before_entry_start']:,} 根。",
            "", "| 指标 | 结果 |", "| --- | ---: |",
            f"| 已平仓笔数 | {summary['closed_trades']} |",
            f"| 净盈利／净亏损笔数 | {summary['winning_trades']} / {summary['losing_trades']} |",
            f"| 扣费后胜率 | {fmt(summary['win_rate_percent'])}% |",
            f"| 已平仓净盈亏 | {fmt(summary['closed_net_pnl'])} USDT |",
            f"| 期末权益（含未实现盈亏） | {fmt(summary['final_equity_mark_to_market'])} USDT |",
            f"| 权益收益率（含未实现盈亏） | {fmt(summary['total_return_percent_mark_to_market'])}% |",
            f"| 收盘权益最大回撤 | {fmt(summary['max_drawdown_percent_at_bar_close'])}% |",
            f"| 净盈利因子 | {fmt(summary['profit_factor_net'], 3)} |",
            f"| 已付手续费 | {fmt(summary['total_fees_paid'])} USDT |",
            f"| 双触退出 K 棒 | {summary['ambiguous_exit_bars']} |",
            f"| 期末未平仓 | {'有，未计入胜率' if summary['open_position'] else '无'} |", "",
            f"初始资金 {cfg['initial_capital']:g} USDT，{sizing_text}；单边手续费 {cfg['fee_percent']:g}%，滑点 {cfg['slippage_ticks']} 个 tick。",
            f"双触处理：`{cfg['intrabar']}`；tick={cfg['tick_size']}，数量步长={cfg['qty_step']}。", "",
            "橙线 SMA10、白线 EMA10、RSI14 是默认值，实际参数以 summary.json 为准。仓位比例不是止损风险比例。",
            "入场在收盘后才生效；入场 K 自己的高低点不能用于提前触发新仓止盈止损。跳空止损按开盘价加不利滑点，跳空越过止盈可按更优开盘价。", "",
            "`stop-first` 对同根双触按止损先到；`tv-path` 按开盘距哪个极值较近决定先走向哪个极值，等距按低点先到。两者都是 OHLC 假设，需要更细周期才能进一步判定。", "",
            "未计永续资金费率，未复刻币安标记价格触发或分档强平；最大回撤仅按收盘权益统计。该结果不能视为与 TradingView 或实盘完全一致。", "",
            "逐笔记录见 trades.csv，权益曲线数据见 equity.csv，完整参数与来源见 summary.json。"]
    (output / "report.md").write_text("\n".join(text) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--start", required=True, help="UTC entry close boundary, inclusive")
    parser.add_argument("--end", required=True, help="UTC entry close boundary, inclusive, matching Pine")
    parser.add_argument("--interval", default="5m")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--direction", choices=["both", "long", "short"], default="both")
    parser.add_argument("--method", choices=["both", "cross", "pullback"], default="both")
    parser.add_argument("--intrabar", choices=["stop-first", "tv-path"], default="stop-first")
    parser.add_argument("--initial-capital", type=float, default=10000)
    parser.add_argument("--position-percent", type=float, default=10)
    parser.add_argument("--fixed-margin", type=float, default=None)
    parser.add_argument("--leverage", type=float, default=1)
    parser.add_argument("--fee-percent", type=float, default=0.05)
    parser.add_argument("--slippage-ticks", type=int, default=0)
    parser.add_argument("--tick-size", type=float, default=0.01)
    parser.add_argument("--qty-step", type=float, default=0.001)
    parser.add_argument("--reward-risk", type=float, default=1.5)
    parser.add_argument("--ema-length", type=int, default=10)
    parser.add_argument("--ma-length", type=int, default=10)
    parser.add_argument("--rsi-length", type=int, default=14)
    parser.add_argument("--long-rsi-min", type=float, default=50)
    parser.add_argument("--long-rsi-max", type=float, default=70)
    parser.add_argument("--short-rsi-min", type=float, default=30)
    parser.add_argument("--short-rsi-max", type=float, default=50)
    args = parser.parse_args()
    try:
        settings = {key: value for key, value in vars(args).items()
                    if key not in {"csv", "output_dir", "start", "end"}}
        cfg = Config(start_ms=utc_ms(args.start), end_ms=utc_ms(args.end), **settings)
        cfg.validate()
        candles = load_candles(args.csv, cfg.interval)
        if candles[0].time_close > cfg.start_ms or candles[-1].time_close < cfg.end_ms:
            raise ValueError("CSV does not cover the requested entry window; download warmup and full requested data")
        summary, trades, curve = run_backtest(candles, cfg)
        summary["data_file"] = str(args.csv.resolve())
        summary["data_sha256"] = hashlib.sha256(args.csv.read_bytes()).hexdigest()
        metadata_path = Path(str(args.csv) + ".metadata.json")
        if metadata_path.exists():
            summary["data_source_metadata"] = json.loads(metadata_path.read_text(encoding="utf-8"))
            recorded_hash = summary["data_source_metadata"].get("output_sha256")
            if recorded_hash and recorded_hash != summary["data_sha256"]:
                raise ValueError("CSV SHA256 differs from its downloader metadata")
        write_outputs(args.output_dir, summary, trades, curve)
        print((args.output_dir / "report.md").read_text(encoding="utf-8"))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
