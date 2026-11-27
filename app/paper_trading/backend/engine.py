"""Incremental, persistable paper broker. Public market data only; no order API.

Closed candles advance indicators/signals. Only subsequently observed quotes
fill orders, trigger brackets, or activate 1.5R. Historical OHLC never fills an
order. The archived backtest remains unchanged and has different fill timing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP


INTERVAL_MS = {"1m": 60000, "3m": 180000, "5m": 300000,
               "15m": 900000, "30m": 1800000, "1h": 3600000,
               "2h": 7200000, "4h": 14400000, "6h": 21600000,
               "8h": 28800000, "12h": 43200000, "1d": 86400000}
CODE_STRATEGY_ID = "ema_ma_rsi_key_candle_same_direction"
EXITS = {"rr15", "trail_ema", "ema_slow", "ema_turn"}
FIELDS = {"open", "high", "low", "close", "volume"}
OPS = {"gt", "gte", "lt", "lte", "cross_up", "cross_down", "between",
       "bullish", "bearish", "wick_above", "wick_below"}
MAX_HISTORY = 1500
WARMUP_BARS = 200


def _number(value, label, minimum=None, maximum=None, integer=False):
    try:
        finite = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except (OverflowError, TypeError):
        finite = False
    if not finite:
        raise ValueError(label + "必须是有限数字")
    if integer and int(value) != value:
        raise ValueError(label + "必须是整数")
    if minimum is not None and value < minimum:
        raise ValueError(label + "不能小于" + str(minimum))
    if maximum is not None and value > maximum:
        raise ValueError(label + "不能大于" + str(maximum))
    return int(value) if integer else float(value)


def _positive(value, label):
    value = _number(value, label)
    if value <= 0:
        raise ValueError(label + "必须大于0")
    return value


def _text(value, label, default=None):
    if value is None and default is not None:
        value = default
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(label + "必须是1至200个字符的文本")
    return value.strip()


def _boolean(value, label):
    if type(value) is not bool:
        raise ValueError(label + "必须是布尔值")
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + "必须是对象")
    return value


def _choice(value, choices, label):
    if not isinstance(value, str) or value not in choices:
        raise ValueError(label + "不支持该选项")
    return value


def _reference(value, refs, label):
    if isinstance(value, str):
        if value not in refs:
            raise ValueError(label + "引用了不存在的字段或指标：" + value)
        return value
    return _number(value, label)


def validate_manual(definition):
    """Validate the deliberately small, single-level manual strategy language."""
    definition = _object(definition, "手动策略")
    indicators = definition.get("indicators", [])
    if not isinstance(indicators, list) or len(indicators) > 20:
        raise ValueError("指标必须是列表，最多20个")
    normalized, refs, types = [], set(FIELDS), {}
    for item in indicators:
        item = _object(item, "指标")
        identifier = _text(item.get("id"), "指标ID")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", identifier) or identifier in refs:
            raise ValueError("指标ID格式错误或重复")
        kind = _choice(item.get("type"), {"EMA", "SMA", "RSI"}, "指标类型")
        source = _choice(item.get("source", "close"), FIELDS - {"volume"}, "指标价格来源")
        length = _number(item.get("length", 14 if kind == "RSI" else 10), "指标周期", 1, 500, True)
        normalized.append({"id": identifier, "type": kind, "length": length, "source": source})
        refs.add(identifier); types[identifier] = kind

    result = {"indicators": normalized}
    for side in ("long", "short", "long_exit", "short_exit"):
        group = _object(definition.get(side, {"enabled": False}), side + "条件")
        enabled = _boolean(group.get("enabled", False), side + "启用")
        logic = _choice(group.get("logic", "all"), {"all", "any"}, "条件组合")
        conditions = group.get("conditions", [])
        if not isinstance(conditions, list) or len(conditions) > 30:
            raise ValueError("条件必须是列表，最多30条")
        if enabled and not conditions:
            raise ValueError(side + "启用时至少需要一个条件")
        cleaned = []
        for condition in conditions:
            condition = _object(condition, "条件")
            op = _choice(condition.get("op"), OPS, "条件关系")
            row = {"op": op}
            if op in {"bullish", "bearish"}:
                cleaned.append(row); continue
            left = condition.get("left", "close")
            if not isinstance(left, str) or left not in refs:
                raise ValueError("条件左值必须引用OHLCV或已有指标")
            row["left"] = left
            row["right"] = _reference(condition.get("right"), refs, "条件右值")
            if op == "between":
                row["upper"] = _reference(condition.get("upper"), refs, "区间上界")
                row["include_lower"] = _boolean(condition.get("include_lower", True), "包含下界")
                row["include_upper"] = _boolean(condition.get("include_upper", True), "包含上界")
                if isinstance(row["right"], (int, float)) and isinstance(row["upper"], (int, float)) and row["right"] > row["upper"]:
                    raise ValueError("区间下界不能大于上界")
            cleaned.append(row)
        result[side] = {"enabled": enabled, "logic": logic, "conditions": cleaned}
    if not result["long"]["enabled"] and not result["short"]["enabled"]:
        raise ValueError("至少启用做多或做空方向")
    exits = _object(definition.get("exit", {}), "退出设置")
    stop_type = _choice(exits.get("stop_type", "percent"), {"percent", "indicator"}, "止损来源")
    stop_percent = _positive(exits.get("stop_percent", 1), "止损百分比")
    if stop_percent >= 100:
        raise ValueError("止损百分比必须小于100")
    stop_indicator = exits.get("stop_indicator", "")
    if not isinstance(stop_indicator, str):
        raise ValueError("止损指标必须是文本")
    if stop_type == "indicator" and types.get(stop_indicator) not in {"EMA", "SMA"}:
        raise ValueError("指标止损须引用EMA或SMA价格指标")
    result["exit"] = {"stop_type": stop_type, "stop_percent": stop_percent,
                      "stop_indicator": stop_indicator,
                      "reward_risk": _positive(exits.get("reward_risk", 1.5), "盈亏比")}
    return result


def validate_config(config):
    config = _object(config, "任务配置")
    symbol = config.get("symbol")
    if (not isinstance(symbol, str) or not 5 <= len(symbol) <= 40 or
            not symbol.endswith("USDT") or not symbol[:-4] or
            not all(char.isalnum() or char == "_" for char in symbol)):
        raise ValueError("币种须为USDT合约代码，字符仅可用字母、数字或下划线")
    interval = _choice(config.get("interval", "4h"), INTERVAL_MS, "K线周期")
    strategy = _object(config.get("strategy"), "策略")
    kind = _choice(strategy.get("kind"), {"code", "manual"}, "策略类型")
    identifier = _text(strategy.get("id", CODE_STRATEGY_ID if kind == "code" else "manual"), "策略ID")
    result_strategy = {"id": identifier, "kind": kind,
                       "name": _text(strategy.get("name", identifier), "策略名称"),
                       "version": _text(strategy.get("version", "1.0.0"), "策略版本")}
    if kind == "code":
        if identifier != CODE_STRATEGY_ID:
            raise ValueError("未知代码策略，请先在后端注册适配器")
        params = _object(strategy.get("params", {}), "策略参数")
        exit_model = _choice(params.get("exit_model", "rr15"), EXITS, "退出方式")
        result_strategy["params"] = {"prior_bars": _number(params.get("prior_bars", 3), "交叉前同向根数", 3, 10, True),
                                     "exit_model": exit_model}
    else:
        result_strategy["params"] = {}
        result_strategy["definition"] = validate_manual(strategy.get("definition"))
    account = _object(config.get("account", {}), "账户设置")
    sizing = _choice(account.get("sizing", "margin"), {"margin", "notional"}, "单笔金额口径")
    result = {"id": _text(config.get("id", "task"), "任务ID"),
              "name": _text(config.get("name", symbol + " 模拟任务"), "任务名称"),
              "symbol": symbol, "interval": interval, "strategy": result_strategy,
              "account": {"initial_capital": _positive(account.get("initial_capital", 10000), "初始本金"),
                          "sizing": sizing,
                          "order_amount": _positive(account.get("order_amount", 200), "每笔金额"),
                          "leverage": _number(account.get("leverage", 10), "杠杆", 1, 125, True),
                          "fee_percent": _number(account.get("fee_percent", .05), "单边手续费百分比", 0, 100),
                          "slippage_ticks": _number(account.get("slippage_ticks", 0), "滑点tick数", 0, 100000, True)}}
    if not math.isfinite(result["account"]["order_amount"] * result["account"]["leverage"]):
        raise ValueError("单笔金额乘杠杆超出数字范围")
    return result


def _round_tick(value, tick):
    step = Decimal(str(tick))
    return float((Decimal(str(value)) / step).to_integral_value(rounding=ROUND_HALF_UP) * step)


def _floor_qty(value, step):
    step = Decimal(str(step))
    return float((Decimal(str(value)) / step).to_integral_value(rounding=ROUND_FLOOR) * step)


def _target(reference, stop, ratio, tick):
    ref = Decimal(str(reference))
    return _round_tick(ref + Decimal(str(ratio)) * (ref - Decimal(str(stop))), tick)


def _hash_config(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _calculate_indicators(specs, confirmed_state, candle):
    """Calculate one candle from a private copy of the confirmed recursion.

    Both preview and confirmation use this function. No engine, bar history,
    account, or strategy state is touched; the caller decides whether to commit
    the returned recursion. Copy only these small per-indicator accumulators.
    """
    indicator_state = copy.deepcopy(confirmed_state)
    values = {}
    for spec in specs:
        key, kind, length = spec["id"], spec["type"], spec["length"]
        price = candle[spec["source"]]
        state = indicator_state.setdefault(key, {})
        if kind == "EMA":
            alpha = 2 / (length + 1)
            state["value"] = price if "value" not in state else alpha * price + (1 - alpha) * state["value"]
            values[key] = state["value"]
        elif kind == "SMA":
            window = state.setdefault("window", [])
            window.append(str(price))
            del window[:-length]
            values[key] = float(sum(Decimal(x) for x in window) / length) if len(window) == length else None
        else:
            previous = state.get("previous")
            if previous is not None:
                gain, loss = max(price - previous, 0), max(previous - price, 0)
                if "up" not in state:
                    gains, losses = state.setdefault("gains", []), state.setdefault("losses", [])
                    gains.append(gain); losses.append(loss)
                    if len(gains) == length:
                        state["up"], state["down"] = sum(gains) / length, sum(losses) / length
                        state.pop("gains", None); state.pop("losses", None)
                else:
                    state["up"] = (state["up"] * (length - 1) + gain) / length
                    state["down"] = (state["down"] * (length - 1) + loss) / length
            state["previous"] = price
            values[key] = None if "up" not in state else (100.0 if state["down"] == 0 else 0.0 if state["up"] == 0 else 100 - 100 / (1 + state["up"] / state["down"]))
    return values, indicator_state


class PaperEngine:
    """One task = one isolated JSON-serializable state machine and account."""

    def __init__(self, config, state=None):
        self.config = validate_config(config)
        self.step_ms = INTERVAL_MS[self.config["interval"]]
        if self.config["strategy"]["kind"] == "code":
            self.indicators = [{"id": "ema", "type": "EMA", "length": 10, "source": "close"},
                               {"id": "sma", "type": "SMA", "length": 10, "source": "close"},
                               {"id": "rsi", "type": "RSI", "length": 14, "source": "close"}]
        else:
            self.indicators = self.config["strategy"]["definition"]["indicators"]
        if state is not None:
            state = copy.deepcopy(_object(state, "运行状态"))
            if state.get("schema_version") != 1 or state.get("config_hash") != _hash_config(self.config):
                raise ValueError("运行状态版本或配置快照不匹配")
            try:
                json.dumps(state, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise ValueError("运行状态不能序列化") from exc
            self.state = state
        else:
            self.state = {"schema_version": 1, "config_hash": _hash_config(self.config),
                          "initialized": False, "filters": None, "indicator_state": {},
                          "bars": [], "bar_count": 0, "last_bar_open_ms": None,
                          "last_bar_close_ms": None, "last_quote_timestamp_ms": None,
                          "last_quote_received_ms": None, "last_price": None,
                          "seen_trade_ids": [], "setup": None, "pending_order": None,
                          "pending_exit": None, "position": None, "trades": [],
                          "cash": self.config["account"]["initial_capital"], "fees_paid": 0.0,
                          "sequence": 0, "equity": [],
                          "peak_equity": self.config["account"]["initial_capital"],
                          "max_drawdown_percent": 0.0, "last_exit_bar_open_ms": None}

    def _event(self, kind, message, stamp, data=None):
        return {"type": kind, "message": message, "time_ms": int(stamp), "data": copy.deepcopy(data or {})}

    def _stamp(self, value, label):
        return _number(value, label, 0, integer=True)

    def _candle(self, candle):
        candle = _object(candle, "K线")
        result = {key: _positive(candle.get(key), "K线" + key) for key in ("open", "high", "low", "close")}
        result["volume"] = _number(candle.get("volume"), "成交量", 0)
        result["open_time_ms"] = self._stamp(candle.get("open_time_ms"), "K线开盘时间")
        result["close_time_ms"] = self._stamp(candle.get("close_time_ms"), "K线收盘时间")
        if result["open_time_ms"] % self.step_ms or result["close_time_ms"] + 1 != result["open_time_ms"] + self.step_ms:
            raise ValueError("K线时间未按运行周期对齐")
        if not result["low"] <= min(result["open"], result["close"]) <= max(result["open"], result["close"]) <= result["high"]:
            raise ValueError("K线高低开收价格关系错误")
        return result

    def _advance(self, candle):
        values, recursion = _calculate_indicators(self.indicators, self.state["indicator_state"], candle)
        self.state["indicator_state"] = recursion
        stored = dict(candle, indicators=values)
        self.state["bars"].append(stored)
        del self.state["bars"][:-MAX_HISTORY]
        self.state["bar_count"] += 1
        self.state["last_bar_open_ms"] = candle["open_time_ms"]
        self.state["last_bar_close_ms"] = candle["close_time_ms"] + 1
        return values

    def preview_indicators(self, candle):
        """Display-only values for the next, possibly incomplete candle.

        Repeated partials always start from the same confirmed state. They do
        not append candles, advance indicators, evaluate signals, or touch the
        simulated account. Stale bars and bars beyond a missing close have no
        preview until their confirmed predecessor is available.
        """
        if not self.state["initialized"]:
            return {}
        candle = self._candle(candle)
        if candle["open_time_ms"] != self.state["last_bar_close_ms"]:
            return {}
        values, _ = _calculate_indicators(self.indicators, self.state["indicator_state"], candle)
        return values

    def bootstrap(self, candles, filters, now_ms):
        if self.state["initialized"]:
            raise ValueError("已有状态不能重复初始化，请使用on_bar补齐")
        now_ms = self._stamp(now_ms, "当前时间")
        if not isinstance(candles, list) or len(candles) < WARMUP_BARS:
            raise ValueError("初始化至少需要200根完整K线")
        filters = _object(filters, "合约限制")
        normalized_filters = {key: _positive(filters.get(key), "合约" + key) for key in ("tick_size", "qty_step", "min_qty", "min_notional")}
        if filters.get("max_qty") is not None:
            normalized_filters["max_qty"] = _positive(filters["max_qty"], "最大数量")
            if normalized_filters["max_qty"] < normalized_filters["min_qty"]:
                raise ValueError("最大数量不能低于最小数量")
        checked = [self._candle(bar) for bar in candles]
        for index, bar in enumerate(checked):
            if bar["close_time_ms"] + 1 > now_ms:
                raise ValueError("初始化包含未收盘或未来K线")
            if index and bar["open_time_ms"] != checked[index-1]["open_time_ms"] + self.step_ms:
                raise ValueError("初始化K线存在缺口、重复或乱序")
        self.state["filters"] = normalized_filters
        for bar in checked:
            self._advance(bar)
        self.state["initialized"] = True
        self.state["last_price"] = checked[-1]["close"]
        self.state["setup"] = None
        self._record_equity(now_ms)
        return [self._event("bootstrap", "指标预热完成；历史K线不产生模拟交易", now_ms,
                            {"warmup_bars": len(checked), "last_bar_close_ms": self.state["last_bar_close_ms"]})]

    def cancel_setup(self, reason):
        events = []
        stamp = self.state["last_quote_received_ms"] or self.state["last_bar_close_ms"] or 0
        if self.state["setup"] is not None or self.state["pending_order"] is not None:
            self.state["setup"] = None
            self.state["pending_order"] = None
            events.append(self._event("setup_cancelled", str(reason), stamp))
        return events

    def _resolve(self, value, row):
        return row.get(value) if isinstance(value, str) else value

    def _condition(self, condition, current, previous):
        op = condition["op"]
        if op in {"bullish", "bearish"}:
            passed = current["close"] > current["open"] if op == "bullish" else current["close"] < current["open"]
            return passed, {"op": op, "open": current["open"], "close": current["close"], "pass": passed}
        left, right = self._resolve(condition["left"], current), self._resolve(condition["right"], current)
        passed = False
        if left is not None and right is not None:
            if op == "gt": passed = left > right
            elif op == "gte": passed = left >= right
            elif op == "lt": passed = left < right
            elif op == "lte": passed = left <= right
            elif op == "wick_above": passed = current["low"] > right
            elif op == "wick_below": passed = current["high"] < right
            elif op == "between":
                upper = self._resolve(condition["upper"], current)
                passed = upper is not None and (left >= right if condition["include_lower"] else left > right) and (left <= upper if condition["include_upper"] else left < upper)
            elif previous is not None:
                old_left, old_right = self._resolve(condition["left"], previous), self._resolve(condition["right"], previous)
                if old_left is not None and old_right is not None:
                    passed = left > right and old_left <= old_right if op == "cross_up" else left < right and old_left >= old_right
        return bool(passed), dict(condition, left_value=left, right_value=right, **{"pass": bool(passed)})

    def _group(self, group, current, previous):
        if not group["enabled"]:
            return False, []
        outcomes = [self._condition(row, current, previous) for row in group["conditions"]]
        passed = all(value for value, _ in outcomes) if group["logic"] == "all" else any(value for value, _ in outcomes)
        return passed, [audit for _, audit in outcomes]

    def _flatten(self, bar):
        return dict(bar, **bar["indicators"]) if bar is not None else None

    def _code_signal(self, bar, received_ms):
        bars = self.state["bars"]
        current = bar["indicators"]
        if any(current.get(key) is None for key in ("ema", "sma", "rsi")) or len(bars) < 2:
            self.state["setup"] = None
            return 0, None, []
        ema, sma, rsi = (current[key] for key in ("ema", "sma", "rsi"))
        previous = bars[-2]["indicators"]
        if previous.get("sma") is None:
            return 0, None, []
        side = 1 if ema > sma else -1 if ema < sma else 0
        setup = self.state["setup"]
        if setup and side != setup["side"]:
            self.state["setup"] = None
        cross = (side == 1 and previous["ema"] <= previous["sma"]) or (side == -1 and previous["ema"] >= previous["sma"])
        events = []
        if cross:
            count = self.config["strategy"]["params"]["prior_bars"] + 1
            points = bars[-(count+1):]
            qualified = len(points) == count + 1 and all(
                old["indicators"].get("sma") is not None and new["indicators"].get("sma") is not None
                and side * (new["indicators"]["ema"] - old["indicators"]["ema"]) > 0
                and side * (new["indicators"]["sma"] - old["indicators"]["sma"]) > 0
                for old, new in zip(points, points[1:]))
            self.state["setup"] = ({"side": side, "trigger_bar_open_ms": bar["open_time_ms"],
                                      "trigger_time_ms": bar["close_time_ms"] + 1,
                                      "directional_changes_checked": count,
                                      "direction_points": [{"time_ms": point["open_time_ms"], **point["indicators"]} for point in points]}
                                     if qualified else None)
            events.append(self._event("setup_armed" if qualified else "cross_rejected",
                                      "交叉符合连续同向条件，等待下一根起首根关键K" if qualified else "交叉前双线同向不满足，本次交叉作废",
                                      received_ms, {"side": "long" if side == 1 else "short", "checks": count}))
        setup = self.state["setup"]
        if not setup or bar["open_time_ms"] <= setup["trigger_bar_open_ms"]:
            return 0, None, events
        candle_pass = bar["close"] > bar["open"] if side == 1 else bar["close"] < bar["open"]
        wick_pass = bar["low"] > max(ema, sma) if side == 1 else bar["high"] < min(ema, sma)
        rsi_pass = 50 < rsi <= 70 if side == 1 else 30 <= rsi < 50
        if not (candle_pass and wick_pass and rsi_pass):
            return 0, None, events
        audit = {"strategy_id": CODE_STRATEGY_ID, "trigger": copy.deepcopy(setup),
                 "key": {key: bar[key] for key in ("open_time_ms", "close_time_ms", "open", "high", "low", "close")},
                 "indicators": dict(current), "signal_time_ms": bar["close_time_ms"] + 1,
                 "checks": [{"label": "均线排列", "pass": side * (ema - sma) > 0},
                            {"label": "关键K阳线" if side == 1 else "关键K阴线", "pass": candle_pass},
                            {"label": "整根K含影线严格位于双线之上" if side == 1 else "整根K含影线严格位于双线之下", "pass": wick_pass},
                            {"label": "50 < RSI ≤ 70" if side == 1 else "30 ≤ RSI < 50", "pass": rsi_pass},
                            {"label": "交叉下一根起首根有效关键K", "pass": True}]}
        return side, audit, events

    def _queue_entry(self, side, audit, bar, received_ms):
        filters = self.state["filters"]
        tick, reference = filters["tick_size"], bar["close"]
        if self.config["strategy"]["kind"] == "code":
            stop = _round_tick(bar["indicators"]["ema"], tick)
            rr = 1.5
            mode = self.config["strategy"]["params"]["exit_model"]
        else:
            settings = self.config["strategy"]["definition"]["exit"]
            raw_stop = (bar["indicators"].get(settings["stop_indicator"]) if settings["stop_type"] == "indicator"
                        else reference * (1 - side * settings["stop_percent"] / 100))
            if raw_stop is None:
                return [self._event("entry_rejected", "止损指标尚未预热", received_ms)]
            stop, rr, mode = _round_tick(raw_stop, tick), settings["reward_risk"], "rr15"
        target = _target(reference, stop, rr, tick)
        risk = side * (reference - stop)
        if stop <= 0 or risk + tick * 1e-9 < tick or target <= 0 or side * (target - reference) <= 0:
            return [self._event("entry_rejected", "初始止损或目标无效，继续等待后续关键K", received_ms)]
        self.state["pending_order"] = {"side": side, "signal_time_ms": bar["close_time_ms"] + 1,
                                       "signal_received_ms": received_ms,
                                       "signal_bar_open_ms": bar["open_time_ms"],
                                       "entry_reference": reference, "initial_stop": stop,
                                       "target": target if mode == "rr15" else None,
                                       "activation_level": target if mode != "rr15" else None,
                                       "exit_model": mode, "audit": audit}
        self.state["setup"] = None
        return [self._event("entry_signal", "收盘信号确认，等待之后实时价格模拟成交", received_ms, self.state["pending_order"])]

    def on_bar(self, candle, received_ms, allow_entries=True, recovery=False):
        if not self.state["initialized"]:
            raise ValueError("请先初始化历史K线和合约限制")
        received_ms = self._stamp(received_ms, "K线接收时间")
        allow_entries = _boolean(allow_entries, "允许开仓")
        recovery = _boolean(recovery, "恢复模式")
        candle = self._candle(candle)
        if candle["close_time_ms"] + 1 > received_ms:
            raise ValueError("不能处理未收盘或未来K线")
        if candle["open_time_ms"] <= self.state["last_bar_open_ms"]:
            return []
        if candle["open_time_ms"] != self.state["last_bar_open_ms"] + self.step_ms:
            raise ValueError("K线存在缺口，请先补齐再推进策略")
        self._advance(candle)
        bar = self.state["bars"][-1]
        events = []
        if recovery:
            events.extend(self.cancel_setup("行情恢复：补齐K线只推进指标，不追溯模拟成交"))
            self.state["pending_exit"] = None
            events.append(self._event("recovery_bar", "恢复K线已补齐；缺口期间触价顺序未知", received_ms,
                                      {"bar_open_ms": bar["open_time_ms"]}))
            return events
        position = self.state["position"]
        if position is not None:
            events.extend(self._close_management(bar, received_ms))
            self.state["setup"] = None
        elif not allow_entries:
            events.extend(self.cancel_setup("已暂停新开仓"))
        elif self.state["pending_order"] is None and self.state["last_exit_bar_open_ms"] != bar["open_time_ms"]:
            if self.config["strategy"]["kind"] == "code":
                side, audit, signal_events = self._code_signal(bar, received_ms)
                events.extend(signal_events)
            else:
                current, previous = self._flatten(bar), self._flatten(self.state["bars"][-2]) if len(self.state["bars"]) > 1 else None
                definition = self.config["strategy"]["definition"]
                long, long_audit = self._group(definition["long"], current, previous)
                short, short_audit = self._group(definition["short"], current, previous)
                side = 1 if long else -1 if short else 0
                audit = {"strategy_id": self.config["strategy"]["id"], "key": {key: bar[key] for key in FIELDS},
                         "signal_time_ms": bar["close_time_ms"] + 1,
                         "indicators": dict(bar["indicators"]), "checks": long_audit if side == 1 else short_audit,
                         "both_sides_matched": long and short}
            if side:
                events.extend(self._queue_entry(side, audit, bar, received_ms))
        self._record_equity(bar["close_time_ms"] + 1)
        return events

    def _close_management(self, bar, received_ms):
        p = self.state["position"]
        if p is None or self.state["pending_exit"] is not None:
            return []
        if bar["close_time_ms"] + 1 <= p["signal_time_ms"]:
            return []
        events = []
        if self.config["strategy"]["kind"] == "manual":
            group = self.config["strategy"]["definition"]["long_exit" if p["side"] == "long" else "short_exit"]
            passed, audit = self._group(group, self._flatten(bar), self._flatten(self.state["bars"][-2]))
            if passed:
                self.state["pending_exit"] = {"reason": "manual_close", "received_ms": received_ms,
                                              "signal_time_ms": bar["close_time_ms"] + 1, "audit": audit}
        elif (p["trail_active"] and
              (p.get("activated_at_ms") is None or p["activated_at_ms"] < bar["close_time_ms"] + 1)):
            side = 1 if p["side"] == "long" else -1
            mode = self.config["strategy"]["params"]["exit_model"]
            ema = bar["indicators"]["ema"]
            if mode == "trail_ema":
                candidate = _round_tick(ema, self.state["filters"]["tick_size"])
                candidate = max(p["stop"], p["entry_fill"], candidate) if side == 1 else min(p["stop"], p["entry_fill"], candidate)
                if candidate != p["stop"]:
                    # A delayed trade from before this close notification must
                    # still see the old active stop, never the new EMA value.
                    p.setdefault("previous_active_stop", p["stop"])
                    p["stop_effective_after_ms"] = received_ms
                    p["stop"] = candidate
                    p["stop_history"].append({"time_ms": received_ms, "signal_time_ms": bar["close_time_ms"] + 1,
                                               "stop": candidate, "reason": "ema_trail", "source_ema": ema})
                    events.append(self._event("stop_updated", "收盘更新EMA止损，仅对后续报价生效", received_ms,
                                              {"stop": candidate, "trade_id": p["id"]}))
            elif mode in {"ema_slow", "ema_turn"} and len(self.state["bars"]) >= 3:
                previous = self.state["bars"][-2]["indicators"]["ema"]
                before = self.state["bars"][-3]["indicators"]["ema"]
                g, previous_g = side * (ema - previous), side * (previous - before)
                passed = previous_g > 0 and 0 < g <= .5 * previous_g if mode == "ema_slow" else g < 0
                if passed:
                    self.state["pending_exit"] = {"reason": mode + "_close", "received_ms": received_ms,
                                                  "signal_time_ms": bar["close_time_ms"] + 1,
                                                  "audit": {"ema": ema, "previous_ema": previous, "previous_previous_ema": before,
                                                            "directional_delta": g, "previous_directional_delta": previous_g,
                                                            "threshold_ratio": .5, "activation_level": p["activation_level"]}}
        if self.state["pending_exit"] is not None:
            events.append(self._event("exit_signal", "收盘退出条件确认，等待后续实时价格成交", received_ms, self.state["pending_exit"]))
        return events

    def _fill_entry(self, order, price, timestamp_ms, received_ms):
        settings, filters = self.config["account"], self.state["filters"]
        side, stop, target = order["side"], order["initial_stop"], order["target"]
        fill = price + side * settings["slippage_ticks"] * filters["tick_size"]
        reason = None
        if fill <= 0 or side * (fill - stop) <= 0:
            reason = "报价已越过初始止损，取消过期入场"
        elif target is not None and side * (target - fill) <= 0:
            reason = "报价已越过固定止盈，取消过期入场"
        if reason:
            self.state["pending_order"] = None
            return [self._event("entry_rejected", reason, received_ms)]
        notional = settings["order_amount"] * settings["leverage"] if settings["sizing"] == "margin" else settings["order_amount"]
        quantity = _floor_qty(notional / fill, filters["qty_step"])
        actual_notional, fee = quantity * fill, quantity * fill * settings["fee_percent"] / 100
        margin = actual_notional / settings["leverage"]
        if quantity <= 0 or Decimal(str(quantity)) < Decimal(str(filters["min_qty"])):
            reason = "下单数量低于合约最小数量"
        elif Decimal(str(quantity)) * Decimal(str(fill)) < Decimal(str(filters["min_notional"])):
            reason = "下单金额低于合约最小名义金额"
        elif filters.get("max_qty") is not None and quantity > filters["max_qty"]:
            reason = "下单数量超过合约最大数量"
        elif margin + fee > self.state["cash"]:
            reason = "模拟账户可用余额不足以支付保证金和开仓手续费"
        self.state["pending_order"] = None
        if reason:
            return [self._event("entry_rejected", reason, received_ms)]
        self.state["sequence"] += 1
        self.state["cash"] -= fee
        self.state["fees_paid"] += fee
        trade = {"id": self.config["id"] + "-" + str(self.state["sequence"]),
                 "side": "long" if side == 1 else "short", "status": "open",
                 "signal_time_ms": order["signal_time_ms"], "signal_received_ms": order["signal_received_ms"],
                 "entry_time_ms": timestamp_ms, "entry_received_ms": received_ms,
                 "entry_reference": order["entry_reference"], "entry_fill": fill,
                 "quantity": quantity, "entry_notional": actual_notional, "margin_used": margin,
                 "initial_stop": stop, "stop": stop, "target": target,
                 "activation_level": order["activation_level"], "trail_active": False,
                 "activated_at_ms": None, "entry_fee": fee, "exit_fee": None,
                 "exit_time_ms": None, "exit_fill": None, "exit_reason": None,
                 "gross_pnl": None, "net_pnl": None, "balance_after": None,
                 "audit": order["audit"], "stop_history": [{"time_ms": timestamp_ms, "stop": stop, "reason": "initial"}]}
        self.state["position"] = trade
        self.state["setup"] = None
        self._record_equity(timestamp_ms)
        return [self._event("entry_fill", "模拟开仓成交", received_ms, trade)]

    def _fill_exit(self, price, timestamp_ms, received_ms, reason, apply_slippage=True):
        p = self.state["position"]
        side = 1 if p["side"] == "long" else -1
        slip = self.config["account"]["slippage_ticks"] * self.state["filters"]["tick_size"]
        fill = price - side * slip if apply_slippage else price
        if fill <= 0:
            raise ValueError("退出滑点导致非正成交价")
        gross = side * p["quantity"] * (fill - p["entry_fill"])
        fee = p["quantity"] * fill * self.config["account"]["fee_percent"] / 100
        self.state["cash"] += gross - fee
        self.state["fees_paid"] += fee
        p.update(status="closed", exit_time_ms=timestamp_ms, exit_received_ms=received_ms,
                 exit_fill=fill, exit_reason=reason, exit_fee=fee, gross_pnl=gross,
                 net_pnl=gross - p["entry_fee"] - fee, balance_after=self.state["cash"])
        if self.state["pending_exit"]:
            p["exit_signal"] = self.state["pending_exit"]
        self.state["trades"].append(p)
        self.state["position"] = self.state["pending_exit"] = None
        # A real quote belongs to the interval in progress at its exchange time.
        self.state["last_exit_bar_open_ms"] = timestamp_ms // self.step_ms * self.step_ms
        self.state["setup"] = None
        self._record_equity(timestamp_ms)
        return [self._event("exit_fill", "模拟平仓成交：" + reason, received_ms, p)]

    def close_position(self, reason="manual_stop"):
        """Queue liquidation; the next fresh real quote still determines its fill."""
        self.cancel_setup("结束任务，取消待开仓")
        if self.state["position"] is None:
            return []
        stamp = self.state["last_quote_received_ms"] or self.state["last_bar_close_ms"] or 0
        self.state["pending_exit"] = {"reason": str(reason), "received_ms": stamp, "signal_time_ms": stamp}
        return [self._event("exit_signal", "等待下一笔实时价格模拟平仓", stamp, self.state["pending_exit"])]

    def on_quote(self, price, timestamp_ms, trade_id=None, received_ms=None):
        if not self.state["initialized"]:
            raise ValueError("请先初始化历史K线和合约限制")
        price = _positive(price, "实时价格")
        timestamp_ms = self._stamp(timestamp_ms, "报价时间")
        received_ms = timestamp_ms if received_ms is None else self._stamp(received_ms, "报价接收时间")
        # Exchange and local clocks may differ. Keep both observed timestamps;
        # never reject an otherwise valid tick just because the local clock lags.
        if trade_id is not None:
            if isinstance(trade_id, bool) or not isinstance(trade_id, (str, int)):
                raise ValueError("成交ID必须是文本或整数")
            trade_id = str(trade_id)
            if trade_id in self.state["seen_trade_ids"]:
                return []
        last = self.state["last_quote_timestamp_ms"]
        if last is not None and timestamp_ms < last:
            return []
        if last is not None and timestamp_ms == last and trade_id is None and price == self.state["last_price"]:
            return []
        if trade_id is not None:
            self.state["seen_trade_ids"].append(trade_id)
            del self.state["seen_trade_ids"][:-2000]
        self.state["last_quote_timestamp_ms"] = timestamp_ms
        self.state["last_quote_received_ms"] = received_ms
        self.state["last_price"] = price
        events = []
        p = self.state["position"]
        if p is not None:
            side = 1 if p["side"] == "long" else -1
            if timestamp_ms >= p.get("stop_effective_after_ms", 0):
                p.pop("previous_active_stop", None)
                p.pop("stop_effective_after_ms", None)
            active_stop = p.get("previous_active_stop", p["stop"])
            if side * (price - active_stop) <= 0:
                events.extend(self._fill_exit(price, timestamp_ms, received_ms, "stop"))
            elif p["target"] is not None and side * (price - p["target"]) >= 0:
                # Model a resting take-profit limit conservatively at its
                # posted price, without assuming improvement on a jumping tick.
                events.extend(self._fill_exit(p["target"], timestamp_ms, received_ms, "target", False))
            elif self.state["pending_exit"] is not None and timestamp_ms >= self.state["pending_exit"]["received_ms"]:
                events.extend(self._fill_exit(price, timestamp_ms, received_ms, self.state["pending_exit"]["reason"]))
            elif p["activation_level"] is not None and not p["trail_active"] and side * (price - p["activation_level"]) >= 0:
                p["trail_active"] = True
                p["activated_at_ms"] = timestamp_ms
                events.append(self._event("exit_activated", "实时触及1.5R，启用后续EMA退出规则", received_ms,
                                          {"trade_id": p["id"], "activation_level": p["activation_level"]}))
        elif self.state["pending_order"] is not None and timestamp_ms >= self.state["pending_order"]["signal_received_ms"]:
            events.extend(self._fill_entry(self.state["pending_order"], price, timestamp_ms, received_ms))
        self._record_equity(timestamp_ms)
        return events

    def _unrealized(self):
        p = self.state["position"]
        if p is None or self.state["last_price"] is None:
            return 0.0
        side = 1 if p["side"] == "long" else -1
        return side * p["quantity"] * (self.state["last_price"] - p["entry_fill"])

    def _record_equity(self, timestamp_ms):
        equity = self.state["cash"] + self._unrealized()
        self.state["peak_equity"] = max(self.state["peak_equity"], equity)
        peak = self.state["peak_equity"]
        dd = 100 * (peak - equity) / peak if peak else 0.0
        self.state["max_drawdown_percent"] = max(self.state["max_drawdown_percent"], dd)
        point = {"time": timestamp_ms // 1000, "equity": equity}
        curve = self.state["equity"]
        if curve and point["time"] == curve[-1]["time"]:
            curve[-1] = point
        elif not curve or point["time"] > curve[-1]["time"]:
            curve.append(point)
        del curve[:-10000]

    def snapshot(self):
        return copy.deepcopy(self.state)

    def account_view(self):
        """Small summary path; do not construct/copy chart history per task."""
        p = self.state["position"]
        initial = self.config["account"]["initial_capital"]
        unrealized = self._unrealized()
        equity = self.state["cash"] + unrealized
        trades = self.state["trades"]
        wins = sum(t["net_pnl"] > 0 for t in trades)
        losses = sum(t["net_pnl"] < 0 for t in trades)
        margin = p["margin_used"] if p else 0.0
        return {"initial_capital": initial, "balance": self.state["cash"], "equity": equity,
                "realized_pnl": sum(t["net_pnl"] for t in trades), "unrealized_pnl": unrealized,
                "margin_used": margin, "available_balance": self.state["cash"] - margin,
                "fees_paid": self.state["fees_paid"], "win_rate": 100 * wins / len(trades) if trades else None,
                "closed_count": len(trades), "winning_count": wins, "losing_count": losses,
                "return_percent": 100 * (equity / initial - 1),
                "max_drawdown_percent": self.state["max_drawdown_percent"]}

    def view(self):
        p = self.state["position"]
        trades = self.state["trades"]
        account = self.account_view()
        colors = ["#ff9f43", "#d8e2f0", "#a78bfa", "#2dd4bf", "#60a5fa"]
        chart_indicators = []
        for index, spec in enumerate(self.indicators):
            chart_indicators.append({"id": spec["id"], "name": spec["type"] + str(spec["length"]),
                                     "type": spec["type"], "pane": "rsi" if spec["type"] == "RSI" else "main",
                                     "color": colors[index % len(colors)],
                                     "data": [{"time": bar["open_time_ms"] // 1000, "value": bar["indicators"][spec["id"]]}
                                              for bar in self.state["bars"] if bar["indicators"].get(spec["id"]) is not None]})
        chart = {"candles": [{"time": bar["open_time_ms"] // 1000,
                               **{key: bar[key] for key in ("open", "high", "low", "close", "volume")},
                               "closed": True} for bar in self.state["bars"]], "indicators": chart_indicators}
        return copy.deepcopy({"account": account, "position": p, "pending_order": self.state["pending_order"],
                              "pending_exit": self.state["pending_exit"], "trades": trades,
                              "equity": self.state["equity"], "chart": chart,
                              "metadata": {"execution": "closed-bar signals, next observed trade-price fills",
                                           "price_tick_size": (self.state["filters"] or {}).get("tick_size"),
                                           "funding_included": False, "mark_price_triggers_included": False,
                                           "liquidation_included": False,
                                           "drawdown": "observed quote equity; gaps are not reconstructed",
                                           "warmup_bars": WARMUP_BARS, "last_bar_close_ms": self.state["last_bar_close_ms"],
                                           "last_quote_timestamp_ms": self.state["last_quote_timestamp_ms"],
                                           "strategy_version": self.config["strategy"]["version"]}})
