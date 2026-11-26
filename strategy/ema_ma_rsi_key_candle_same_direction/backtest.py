#!/usr/bin/env python3
"""Frozen OHLC simulation core for the same-direction EMA/SMA/RSI strategy.

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
from dataclasses import asdict, dataclass, field
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
    method: str = "cross"
    reward_risk: float = 1.5
    initial_capital: float = 10000
    position_percent: float = 10
    fixed_margin: Optional[float] = None
    leverage: float = 1
    fee_percent: float = 0.05
    slippage_ticks: int = 0
    tick_size: float = 0.01
    qty_step: float = 0.001
    min_qty: float = 0.0
    min_notional: float = 0.0
    intrabar: str = "stop-first"
    entry_rules: str = "directional_cross"
    cross_direction_bars: int = 4
    require_key_direction: bool = False
    exit_mode: str = "fixed"
    trail_activation_r: float = 1.5
    ema_slowdown_ratio: float = 0.5
    momentum_activation_required: bool = True

    def validate(self):
        if self.exit_mode not in {"fixed", "ema_trail", "ema_close", "ema_slow", "ema_turn"}:
            raise ValueError("invalid exit mode")
        if not math.isfinite(self.ema_slowdown_ratio) or not 0 < self.ema_slowdown_ratio < 1:
            raise ValueError("EMA slowdown ratio must be between zero and one")
        if type(self.momentum_activation_required) is not bool:
            raise ValueError("momentum_activation_required must be boolean")
        if not math.isfinite(self.trail_activation_r) or self.trail_activation_r <= 0:
            raise ValueError("trail activation R must be positive")
        if self.start_ms >= self.end_ms:
            raise ValueError("start must precede end")
        if min(self.ema_length, self.ma_length, self.rsi_length) < 1:
            raise ValueError("indicator lengths must be positive")
        if self.entry_rules not in {"confirmed", "legacy", "directional_cross"}:
            raise ValueError("invalid entry rules")
        if type(self.cross_direction_bars) is not int or not 1 <= self.cross_direction_bars <= 20:
            raise ValueError("cross_direction_bars must be an integer from 1 to 20")
        if type(self.require_key_direction) is not bool:
            raise ValueError("require_key_direction must be boolean")
        if self.entry_rules == "directional_cross" and self.method != "cross":
            raise ValueError("directional_cross supports the cross method only")
        if self.entry_rules in {"legacy", "directional_cross"}:
            for lo, hi in [(self.long_rsi_min, self.long_rsi_max),
                           (self.short_rsi_min, self.short_rsi_max)]:
                if not (0 <= lo <= hi <= 100):
                    raise ValueError("invalid RSI bounds")
        for value in [self.reward_risk, self.initial_capital, self.tick_size,
                      self.qty_step, self.position_percent]:
            if not math.isfinite(value) or value <= 0:
                raise ValueError("capital, size, tick, quantity step and R must be positive")
        if any(not math.isfinite(value) or value < 0 for value in (self.min_qty, self.min_notional)):
            raise ValueError("minimum quantity and notional must be finite and nonnegative")
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
    target: Optional[float]
    quantity: float
    entry_fee: float
    audit: Optional[dict] = None
    initial_stop: Optional[float] = None
    initial_risk: Optional[float] = None
    activation_level: Optional[float] = None
    trail_active: bool = False
    activated_at: Optional[int] = None
    stop_history: list = field(default_factory=list)


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
        # half-tick before the line is displayed or used in comparisons.
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
        if p.target is not None and bar.open >= p.target:
            return bar.open, "target_gap", False
        stop_hit, target_hit = bar.low <= p.stop, p.target is not None and bar.high >= p.target
    else:
        if bar.open >= p.stop:
            return bar.open, "stop_gap", False
        if p.target is not None and bar.open <= p.target:
            return bar.open, "target_gap", False
        stop_hit, target_hit = bar.high >= p.stop, p.target is not None and bar.low <= p.target
    if not stop_hit and not target_hit:
        return None
    if stop_hit and target_hit:
        # TV-style OHLC path assumption; equal distances explicitly choose low first.
        high_first = abs(bar.high - bar.open) < abs(bar.open - bar.low)
        target_first = policy == "tv-path" and (high_first == (p.side == 1))
        return (p.target, "target_both", True) if target_first else (p.stop, "stop_both", True)
    return (p.stop, "stop", False) if stop_hit else (p.target, "target", False)


def initialize_trailing(position, cfg):
    position.initial_stop = position.stop
    position.initial_risk = abs(position.reference - position.stop)
    position.activation_level = target_for_reference(position.reference, position.stop, cfg.trail_activation_r, cfg.tick_size)
    position.target = None
    position.stop_history = [{"updated_at": position.entry_time_ms // 1000,
                              "effective_from": position.entry_time_ms // 1000,
                              "stop": position.initial_stop if cfg.exit_mode in {"ema_trail", "ema_close", "ema_slow", "ema_turn"} else position.stop, "target": None, "reason": "initial"}]


def update_trailing(position, bar, indicator, cfg):
    """Called after checking an existing position against the old stop.

    Each completed-bar update is effective only on the next candle. Range
    information from this bar can activate a new stop but cannot fill it.
    """
    if not position.trail_active:
        reached = (bar.high >= position.activation_level if position.side == 1
                   else bar.low <= position.activation_level)
        if not reached:
            return
        position.trail_active = True
        position.activated_at = bar.time_close // 1000
    ema_stop = round_tick(indicator.ema, cfg.tick_size)
    new_stop = (max(position.stop, position.entry, ema_stop) if position.side == 1
                else min(position.stop, position.entry, ema_stop))
    if new_stop != position.stop:
        position.stop = new_stop
        position.stop_history.append({"updated_at": bar.time_close // 1000,
                                      "effective_from": bar.time_close // 1000,
                                      "stop": new_stop, "target": None,
                                      "reason": "ema_trail", "source_bar_time": bar.open_time_ms // 1000,
                                      "source_ema": indicator.ema})


def close_exit_signal(position, bar, indicator, cfg):
    """After the previously active stop check, act only at this confirmed close.

    The entry-price floor means a surviving first activation always tightens
    compared with the initial stop. The candidate is not an active order.
    """
    if not position.trail_active:
        reached = (bar.high >= position.activation_level if position.side == 1
                   else bar.low <= position.activation_level)
        if not reached:
            return None
        position.trail_active = True
        position.activated_at = bar.time_close // 1000
    ema_stop = round_tick(indicator.ema, cfg.tick_size)
    candidate = (max(position.stop, position.entry, ema_stop) if position.side == 1
                 else min(position.stop, position.entry, ema_stop))
    tightens = position.side * (candidate - position.stop) > 0
    if not tightens:
        return None
    return {"signal_time": bar.time_close // 1000,
            "source_bar_time": bar.open_time_ms // 1000,
            "ema": indicator.ema, "rounded_ema": ema_stop,
            "previous_active_stop": position.stop,
            "candidate_stop": candidate, "close": bar.close,
            "activation_level": position.activation_level,
            "activation_reached": True, "strictly_tightens": True,
            "candidate_posted_as_stop": False}


def momentum_exit_signal(position, bar, indicator, previous, before_previous, cfg):
    """Evaluate a slope signal only at the surviving post-entry bar's close.

    The original stop is never moved by either new exit. The activation is a
    persistent condition and final EMA values never act at a candle's open.
    """
    if not position.trail_active:
        reached = (bar.high >= position.activation_level if position.side == 1
                   else bar.low <= position.activation_level)
        if cfg.momentum_activation_required and not reached:
            return None
        position.trail_active = True
        position.activated_at = bar.time_close // 1000
    if previous is None or before_previous is None:
        return None
    delta = indicator.ema - previous.ema
    previous_delta = previous.ema - before_previous.ema
    favorable = position.side * delta
    previous_favorable = position.side * previous_delta
    ratio = abs(delta) / abs(previous_delta) if previous_delta != 0 else None
    slow = previous_favorable > 0 and 0 < favorable <= cfg.ema_slowdown_ratio * previous_favorable
    turn = favorable < 0
    passed = slow if cfg.exit_mode == "ema_slow" else turn
    if not passed:
        return None
    return {"condition": cfg.exit_mode,
            "signal_time": bar.time_close // 1000, "source_bar_time": bar.open_time_ms // 1000,
            "ema": indicator.ema, "previous_ema": previous.ema,
            "previous_previous_ema": before_previous.ema, "delta": delta,
            "previous_delta": previous_delta, "directional_delta": favorable,
            "previous_directional_delta": previous_favorable, "slowdown_ratio": ratio,
            "threshold_ratio": cfg.ema_slowdown_ratio,
            "condition_pass": True, "actual_close": bar.close,
            "activation_required": cfg.momentum_activation_required,
            "activation_level": position.activation_level, "activation_reached": position.trail_active,
            "activated_at": position.activated_at, "initial_stop": position.initial_stop, "active_stop": position.stop,
            "candidate_posted_as_stop": False, "confirmed_close_only": True}


def trail_trade_fields(position):
    return {"exit_active_stop": position.stop, "initial_stop": position.initial_stop,
            "initial_risk": position.initial_risk, "activation_level": position.activation_level,
            "trail_active": position.trail_active, "activated_at": position.activated_at,
            "stop_history": position.stop_history}


def rsi_passes(value, side, cfg):
    if cfg.entry_rules == "confirmed":
        return value > 50 if side == 1 else value < 50
    lo, hi = (cfg.long_rsi_min, cfg.long_rsi_max) if side == 1 else (cfg.short_rsi_min, cfg.short_rsi_max)
    if cfg.entry_rules == "directional_cross":
        return lo < value <= hi if side == 1 else lo <= value < hi
    return lo <= value <= hi


def joint_direction(current, previous, side):
    """Use completed line values; flat or oppositely directed lines fail."""
    return (previous is not None and previous.sma is not None and current.sma is not None
            and side * (current.ema - previous.ema) > 0
            and side * (current.sma - previous.sma) > 0)


def cross_direction_ready(indicators, index, side, cfg):
    """N directional changes ending on the cross; the default includes 3 prior bars."""
    first = index - cfg.cross_direction_bars + 1
    if first < 1:
        return False
    return all(joint_direction(indicators[i], indicators[i - 1], side)
               for i in range(first, index + 1))


def cross_entry_ready(index, trigger_index, current, previous, side, cfg):
    if trigger_index is None:
        return False
    if cfg.entry_rules == "legacy":
        return True
    if cfg.entry_rules == "directional_cross":
        return (index > trigger_index and
                (not cfg.require_key_direction or joint_direction(current, previous, side)))
    return index > trigger_index and joint_direction(current, previous, side)


def entry_audit(candles, indicators, index, trigger_index, side, method, cfg):
    """Record the exact signal values; chart dates always refer to bar OPENS."""
    bar, ind = candles[index], indicators[index]
    trigger, trigger_ind = candles[trigger_index], indicators[trigger_index]
    previous = indicators[trigger_index - 1] if trigger_index else None
    long = side == 1
    cross = method.endswith("1")
    confirmed = cfg.entry_rules == "confirmed"
    directional = cfg.entry_rules == "directional_cross"
    # Orange is the fast EMA; white is the slow simple MA (SMA).
    trend_ok = ind.ema > ind.sma if long else ind.ema < ind.sma
    candle_ok = bar.close > bar.open if long else bar.close < bar.open
    wick_ok = bar.low > max(ind.ema, ind.sma) if long else bar.high < min(ind.ema, ind.sma)
    lo, hi = (cfg.long_rsi_min, cfg.long_rsi_max) if long else (cfg.short_rsi_min, cfg.short_rsi_max)
    relation = ">" if long else "<"
    same_bar_allowed = cross and cfg.entry_rules == "legacy"
    earlier_keys = 0
    for i in range(trigger_index if same_bar_allowed else trigger_index + 1, index):
        candidate, values = candles[i], indicators[i]
        key_ok = (candidate.close > candidate.open and candidate.low > max(values.sma, values.ema)
                  and values.ema > values.sma if long else
                  candidate.close < candidate.open and candidate.high < min(values.sma, values.ema)
                  and values.ema < values.sma)
        if not key_ok or not rsi_passes(values.rsi, side, cfg):
            continue
        if cross and not cross_entry_ready(i, trigger_index, values, indicators[i - 1], side, cfg):
            continue
        candidate_stop = round_tick(values.ema, cfg.tick_size)
        candidate_target = target_for_reference(candidate.close, candidate_stop, cfg.reward_risk, cfg.tick_size)
        valid_bracket = (side * (candidate.close - candidate_stop) + cfg.tick_size * 1e-9 >= cfg.tick_size
                         and candidate_target > 0 and side * (candidate_target - candidate.close) > 0)
        earlier_keys += bool(valid_bracket)
    checks = [
        {"label": "均线排列", "value": f"橙 EMA {ind.ema:.5f} {relation} 白 SMA {ind.sma:.5f}", "pass": trend_ok},
        {"label": "关键 K 阳线" if long else "关键 K 阴线",
         "value": f"收 {bar.close:.2f} {relation} 开 {bar.open:.2f}", "pass": candle_ok},
        {"label": "整根影线在两线上方" if long else "整根影线在两线下方",
         "value": (f"低 {bar.low:.2f} > 两线最高 {max(ind.ema, ind.sma):.5f}" if long else
                   f"高 {bar.high:.2f} < 两线最低 {min(ind.ema, ind.sma):.5f}"), "pass": wick_ok},
        {"label": "RSI 严格方向阈值" if confirmed else "RSI 区间（50边界排除）" if directional else "RSI 区间（含边界）",
         "value": (f"RSI {ind.rsi:.5f} {relation} 50" if confirmed else
                   f"{lo:g} {'<' if long else '≤'} {ind.rsi:.5f} {'≤' if long else '<'} {hi:g}" if directional else
                   f"{lo:g} ≤ {ind.rsi:.5f} ≤ {hi:g}"),
         "pass": rsi_passes(ind.rsi, side, cfg)},
        {"label": "触发至入场时序", "value": f"触发后 {index-trigger_index} 根；{'允许触发当根' if same_bar_allowed else '必须晚于触发 K'}",
         "pass": index >= trigger_index if same_bar_allowed else index > trigger_index},
        {"label": "等待期间均线方向有效", "value": f"核对 {index-trigger_index+1} 根",
         "pass": all(v.sma is not None and (v.ema > v.sma if long else v.ema < v.sma)
                     for v in indicators[trigger_index:index+1])},
        {"label": "首根合格关键 K", "value": f"本次触发后，此前符合关键 K 且止盈止损有效的 K：{earlier_keys} 根",
         "pass": earlier_keys == 0},
    ]
    if cross:
        triggered = previous is not None and previous.sma is not None and (
            trigger_ind.ema > trigger_ind.sma and previous.ema <= previous.sma if long else
            trigger_ind.ema < trigger_ind.sma and previous.ema >= previous.sma)
        checks.append({"label": "方式一交叉触发", "value": "橙 EMA 上穿白 SMA" if long else "橙 EMA 下穿白 SMA", "pass": triggered})
        if directional:
            for offset in range(cfg.cross_direction_bars):
                j = trigger_index - offset
                current_line = indicators[j]
                prior_line = indicators[j - 1] if j > 0 else None
                checks.append({
                    "label": "交叉当根双线同向" if offset == 0 else f"交叉前{offset}根双线同向",
                    "value": (f"EMA {current_line.ema:.5f} {relation} {prior_line.ema:.5f}，"
                              f"MA {current_line.sma:.5f} {relation} {prior_line.sma:.5f}"
                              if prior_line is not None and prior_line.sma is not None else "均线历史不足"),
                    "pass": joint_direction(current_line, prior_line, side),
                })
            if cfg.require_key_direction:
                previous_key = indicators[index - 1]
                checks.append({"label": "关键 K 当根双线同向",
                               "value": f"EMA {ind.ema:.5f} {relation} {previous_key.ema:.5f}，MA {ind.sma:.5f} {relation} {previous_key.sma:.5f}",
                               "pass": joint_direction(ind, previous_key, side)})
        if confirmed:
            previous_key = indicators[index - 1]
            checks.append({
                "label": "方式一双线斜率同向",
                "value": (f"EMA {ind.ema:.5f} {relation} {previous_key.ema:.5f}，"
                          f"MA {ind.sma:.5f} {relation} {previous_key.sma:.5f}（上一根收盘）"),
                "pass": cross_entry_ready(index, trigger_index, ind, previous_key, side, cfg),
            })
    else:
        triggered = (trigger.close < trigger.open and trigger.close < trigger_ind.sma and trigger_ind.ema > trigger_ind.sma
                     if long else trigger.close > trigger.open and trigger.close > trigger_ind.sma and trigger_ind.ema < trigger_ind.sma)
        checks.append({"label": "方式二回踩／反弹触发", "value":
                       f"开 {trigger.open:.2f}，收 {trigger.close:.2f}，白 SMA {trigger_ind.sma:.5f}", "pass": triggered})
    audit = {
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
    if confirmed:
        audit["key"].update(previous_ema=indicators[index - 1].ema, previous_sma=indicators[index - 1].sma)
    if directional:
        audit["trigger"].update(
            cross_direction_bars=cfg.cross_direction_bars,
            direction_points=[{"bar_time": candles[j].open_time_ms // 1000,
                               "ema": indicators[j].ema, "sma": indicators[j].sma}
                              for j in range(trigger_index - cfg.cross_direction_bars, trigger_index + 1)],
            direction_qualified=cross_direction_ready(indicators, trigger_index, side, cfg))
        audit["key"].update(previous_ema=indicators[index - 1].ema, previous_sma=indicators[index - 1].sma,
                             direction_required=cfg.require_key_direction)
    return audit


def run_backtest(candles, cfg, capture_audit=False):
    cfg.validate()
    cash = cfg.initial_capital
    position = None
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
            close_signal = None
            momentum_signal = None
            if resolution is None and cfg.exit_mode == "ema_close":
                close_signal = close_exit_signal(position, bar, ind, cfg)
                if close_signal is not None:
                    resolution = (bar.close, "ema_tighten_close", False)
            if resolution is None and cfg.exit_mode in {"ema_slow", "ema_turn"}:
                momentum_signal = momentum_exit_signal(position, bar, ind,
                    indicators[index-1] if index else None,
                    indicators[index-2] if index > 1 else None, cfg)
                if momentum_signal is not None:
                    resolution = (bar.close, "ema_slow_close" if cfg.exit_mode == "ema_slow" else "ema_turn_close", False)
            if resolution is not None:
                raw_exit, reason, ambiguous = resolution
                exit_fill = raw_exit - position.side * slip if reason.startswith("stop") or reason in {"ema_tighten_close", "ema_slow_close", "ema_turn_close"} else raw_exit
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
                    "stop": position.initial_stop if cfg.exit_mode in {"ema_trail", "ema_close", "ema_slow", "ema_turn"} else position.stop,
                    "target": position.target,
                    "quantity": position.quantity,
                    "entry_notional": position.quantity * position.entry,
                    "margin_used": position.quantity * position.entry / cfg.leverage,
                    "leverage": cfg.leverage,
                    "exit_bar_open_utc": utc_text(bar.open_time_ms),
                    "exit_bar_close_utc": utc_text(bar.time_close),
                    "exit_exact_time_utc": (utc_text(bar.open_time_ms) if reason.endswith("gap") else
                                            utc_text(bar.time_close) if reason in {"ema_tighten_close", "ema_slow_close", "ema_turn_close"} else None),
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
                if cfg.exit_mode in {"ema_trail", "ema_close", "ema_slow", "ema_turn"}:
                    trades[-1].update(trail_trade_fields(position))
                if cfg.exit_mode == "ema_close":
                    trades[-1]["close_signal"] = close_signal
                if cfg.exit_mode in {"ema_slow", "ema_turn"}:
                    trades[-1]["momentum_signal"] = momentum_signal
                if capture_audit:
                    trades[-1]["_audit"] = position.audit
                position = None
                closed_this_bar = True

        if position is not None and cfg.exit_mode == "ema_trail":
            update_trailing(position, bar, ind, cfg)

        ready = ind.sma is not None and ind.rsi is not None
        # Match the companion Pine time_close >= start and <= end exactly.
        in_window = cfg.start_ms <= bar.time_close <= cfg.end_ms
        if not ready or not in_window or position is not None or closed_this_bar:
            long_cross_bar = short_cross_bar = None
            long_pullback = short_pullback = None
        else:
            orange, white = ind.ema, ind.sma
            long_trend, short_trend = orange > white, orange < white
            if not long_trend:
                long_pullback = None
                long_cross_bar = None
            if not short_trend:
                short_pullback = None
                short_cross_bar = None
            cross_up = prev is not None and prev.sma is not None and orange > white and prev.ema <= prev.sma
            cross_down = prev is not None and prev.sma is not None and orange < white and prev.ema >= prev.sma
            if long_enabled and cross_enabled and cross_up:
                if cfg.entry_rules != "directional_cross" or cross_direction_ready(indicators, index, 1, cfg):
                    long_cross_bar = index
                else:
                    long_cross_bar = None
                    rejected["cross_without_joint_direction"] += 1
            if short_enabled and cross_enabled and cross_down:
                if cfg.entry_rules != "directional_cross" or cross_direction_ready(indicators, index, -1, cfg):
                    short_cross_bar = index
                else:
                    short_cross_bar = None
                    rejected["cross_without_joint_direction"] += 1
            if (long_enabled and pullback_enabled and long_trend and bar.close < bar.open
                    and bar.close < white and long_pullback is None):
                long_pullback = index
            if (short_enabled and pullback_enabled and short_trend and bar.close > bar.open
                    and bar.close > white and short_pullback is None):
                short_pullback = index
            long_key = (bar.close > bar.open and bar.low > max(orange, white)
                        and rsi_passes(ind.rsi, 1, cfg))
            short_key = (bar.close < bar.open and bar.high < min(orange, white)
                         and rsi_passes(ind.rsi, -1, cfg))
            long_via_cross = cross_enabled and cross_entry_ready(index, long_cross_bar, ind, prev, 1, cfg)
            short_via_cross = cross_enabled and cross_entry_ready(index, short_cross_bar, ind, prev, -1, cfg)
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
                    elif Decimal(str(quantity)) < Decimal(str(cfg.min_qty)):
                        rejected["below_minimum_quantity"] += 1
                    elif Decimal(str(quantity)) * Decimal(str(fill)) < Decimal(str(cfg.min_notional)):
                        rejected["below_minimum_notional"] += 1
                    elif margin_used + entry_fee > cash:
                        rejected["insufficient_margin_and_fee" if cfg.fixed_margin is not None
                                 else "insufficient_unlevered_capital"] += 1
                    else:
                        trigger_index = (long_cross_bar if side == 1 else short_cross_bar) if entry_method.endswith("1") else (
                            long_pullback if side == 1 else short_pullback)
                        audit = entry_audit(candles, indicators, index, trigger_index, side, entry_method, cfg) if capture_audit else None
                        position = Position(side, entry_method, index, bar.time_close,
                                            bar.close, fill, stop, target, quantity, entry_fee, audit)
                        if cfg.exit_mode in {"ema_trail", "ema_close", "ema_slow", "ema_turn"}:
                            initialize_trailing(position, cfg)
                        cash -= entry_fee
                    # Pine clears setups when an order is SUBMITTED, even if
                    # the broker subsequently rejects its quantity or margin.
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
        "strategy_version": ("ema-orange-sma-white-v4-directional-cross" if cfg.entry_rules == "directional_cross" else
                             "ema-orange-sma-white-v3" if cfg.entry_rules == "confirmed" else "ema-orange-sma-white-v2"),
        "strategy_mapping": {"orange": "EMA", "white": "SMA", "initial_stop": "EMA", "exit_mode": cfg.exit_mode},
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
            "EMA trailing stop updates at completed closes after the old stop check and is effective next candle; no retroactive range fill.",
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
    text = [f"# 币安 {summary.get('symbol', 'ETHUSDT')} 永续历史回测", "",
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
            "橙线 EMA10、白线 SMA10、RSI14；初始止损取关键 K 当时橙色 EMA。实际参数及策略版本见 summary.json。",
            (f"固定止盈 {cfg['reward_risk']:g}R。" if cfg.get("exit_mode") == "fixed" else
             "无固定止盈；达到1.5R启用价且旧止损未触发，若收盘候选EMA止损可收紧，直接按该根收盘价全平，候选价不挂单。因保本位约束首次有效启用总会收紧。" if cfg.get("exit_mode") == "ema_close" else
             "无固定止盈；达到1.5R且未先触初始止损后，EMA仍顺势但本根变化幅度不超过上一根50%时按确认收盘价平仓；初始止损固定，无EMA追踪挂单。" if cfg.get("exit_mode") == "ema_slow" else
             "无固定止盈；达到1.5R且未先触初始止损后，多单EMA下降或空单EMA上升时按确认收盘价平仓；初始止损固定，无EMA追踪挂单。" if cfg.get("exit_mode") == "ema_turn" else
             "无固定止盈；达到1.5初始R后在收盘按EMA收紧止损，下一根生效，且不低于价格保本位（未扣费）。"),
            (f"仅方式一：交叉前连续 {cfg.get('cross_direction_bars', 4)-1} 根及交叉当根，双线都须沿交易方向运行。"
             "混向或平线交叉作废，不会因后续方向恢复而补充启动。交叉当根只触发等待，从下一根起找首根合格关键 K。"
             f"多单 RSI 为 ({cfg['long_rsi_min']:g}, {cfg['long_rsi_max']:g}]，空单为 [{cfg['short_rsi_min']:g}, {cfg['short_rsi_max']:g})。"
             + ("关键 K 当根还须双线同向。" if cfg.get('require_key_direction') else "双线同向仅在交叉触发阶段检查，关键 K 不另加方向或斜率幅度要求。")
             + "无量比过滤；均线相等或反向时取消等待。"
             if cfg.get("entry_rules") == "directional_cross" else
             "方式一从均线交叉的下一根开始等待。关键 K 收盘时，多单要求双线较前一根同升，空单要求两线同跌。"
             "斜率或关键 K 条件未满足时继续等待，反向排列或两线相等时取消等待。两种方式均要求多单 RSI 大于 50、空单 RSI 小于 50。"
             if cfg.get("entry_rules") == "confirmed" else
             f"方式一允许交叉当根入场。多单 RSI 范围 {cfg['long_rsi_min']:g}–{cfg['long_rsi_max']:g}，"
             f"空单 {cfg['short_rsi_min']:g}–{cfg['short_rsi_max']:g}，均含边界。"),
            "入场在收盘后才生效；入场 K 自己的高低点不能用于提前触发新仓止盈止损。跳空止损按开盘价加不利滑点，跳空越过止盈可按更优开盘价。", "",
            "`stop-first` 对同根双触按止损先到；`tv-path` 按开盘距哪个极值较近决定先走向哪个极值，等距按低点先到。两者都是 OHLC 假设，需要更细周期才能进一步判定。", "",
            "未计永续资金费率，未复刻币安标记价格触发或分档强平；最大回撤仅按收盘权益统计。该结果不能视为与 TradingView 或实盘完全一致。", "",
            "逐笔记录见 trades.csv，权益曲线数据见 equity.csv，完整参数与来源见 summary.json。"]
    (output / "report.md").write_text("\n".join(text) + "\n", encoding="utf-8")


# This module is a preserved simulation core. The supported strategy interface is
# run_backtest.py, which fixes the current rules and exposes only four exit modes.
if __name__ == "__main__":
    raise SystemExit("Use python3 run_backtest.py --help for the supported strategy CLI.")
