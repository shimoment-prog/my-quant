"""Read-only Binance USD-M market data; this module has no account API.

REST prices remain decimal strings. Each MarketFeed can be shared by tasks for
one symbol/interval, while the caller owns all strategy and financial state.
"""
from __future__ import annotations

import importlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Optional, Tuple


INTERVALS = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
             "6h", "8h", "12h", "1d"]
INTERVAL_MS = dict(zip(INTERVALS, [60_000, 180_000, 300_000, 900_000,
                                 1_800_000, 3_600_000, 7_200_000, 14_400_000,
                                 21_600_000, 28_800_000, 43_200_000, 86_400_000]))
REST_URL = "https://fapi.binance.com"
WEBSOCKET_URL = "wss://fstream.binance.com/stream?streams="
LOGGER = logging.getLogger(__name__)
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class MarketDataError(ValueError):
    """An upstream response is unavailable or not safe to use as market data."""


class _RequestWeightBudget:
    """One process-wide rolling budget, including failed request attempts.

    Waiting outside the lock allows all feeds to share the same allowance.
    Clock/wait injection keeps budget and cooldown checks entirely offline.
    """

    def __init__(self, capacity: int = 1800, window_seconds: float = 60,
                 clock: Optional[Callable[[], float]] = None,
                 wait: Optional[Callable[[float], Any]] = None):
        if capacity <= 0 or window_seconds <= 0:
            raise ValueError("request budget and window must be positive")
        self.capacity = capacity
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._wait = wait or time.sleep
        self._requests = deque()
        self._used = 0
        self._blocked_until = 0.0
        self._lock = threading.Lock()

    def acquire(self, weight: int) -> None:
        if not isinstance(weight, int) or isinstance(weight, bool) or not 0 < weight <= self.capacity:
            raise ValueError("request weight exceeds available budget")
        while True:
            with self._lock:
                now = self._clock()
                while self._requests and self._requests[0][0] <= now - self.window_seconds:
                    self._used -= self._requests.popleft()[1]
                if now >= self._blocked_until and self._used + weight <= self.capacity:
                    self._requests.append((now, weight))
                    self._used += weight
                    return
                delay = max(0.0, self._blocked_until - now)
                if self._used + weight > self.capacity:
                    delay = max(delay, self._requests[0][0] + self.window_seconds - now)
            self._wait(min(max(delay, 0.001), 1.0))

    def defer(self, seconds: float) -> None:
        """Apply an exchange 429 Retry-After cooldown to every local client."""
        with self._lock:
            self._blocked_until = max(self._blocked_until, self._clock() + seconds)


_REQUEST_WEIGHT_BUDGET = _RequestWeightBudget()


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise MarketDataError("{} must be an integer".format(name))
    if isinstance(value, str) and not re.fullmatch(r"-?\d+", value):
        raise MarketDataError("{} must be an integer".format(name))
    result = int(value)
    if result < 0:
        raise MarketDataError("{} must be nonnegative".format(name))
    return result


def _decimal(value: Any, name: str, allow_zero: bool = False) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise MarketDataError("{} must be a decimal".format(name))
    text = str(value)
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise MarketDataError("{} must be a decimal".format(name)) from exc
    if not number.is_finite() or number < 0 or (number == 0 and not allow_zero):
        raise MarketDataError("{} must be finite and {}".format(
            name, "nonnegative" if allow_zero else "positive"))
    return text


def _symbol(value: Any) -> str:
    if (not isinstance(value, str) or not 2 <= len(value) <= 40 or value != value.upper()
            or not all(char.isalnum() or char == "_" for char in value)):
        raise MarketDataError("invalid Binance symbol")
    return value


def validate_candle(candle: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized candle, rejecting nonfinite or inconsistent data."""
    if not isinstance(candle, dict):
        raise MarketDataError("candle must be an object")
    try:
        result = {name: _integer(candle[name], name)
                  for name in ("open_time_ms", "close_time_ms")}
        for name in ("open", "high", "low", "close", "volume"):
            result[name] = _decimal(candle[name], name, allow_zero=name == "volume")
    except KeyError as exc:
        raise MarketDataError("candle missing {}".format(exc.args[0])) from exc
    if result["close_time_ms"] <= result["open_time_ms"]:
        raise MarketDataError("candle close must follow open")
    opened, high, low, closed = [Decimal(result[name])
                                for name in ("open", "high", "low", "close")]
    if not low <= min(opened, closed) <= max(opened, closed) <= high:
        raise MarketDataError("inconsistent candle OHLC")
    return result


def parse_kline(row: Any) -> Dict[str, Any]:
    """Parse the public REST /klines array without assuming it is closed."""
    if not isinstance(row, (list, tuple)) or len(row) < 7:
        raise MarketDataError("kline must contain at least seven fields")
    return validate_candle(dict(zip(
        ("open_time_ms", "open", "high", "low", "close", "volume", "close_time_ms"),
        row[:7])))


def map_message(message: Any, received_ms: int) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Map one combined/raw WS message to a quote, closed bar, or display bar.

    Unknown control events return None. Malformed supported data raises, so the
    feed can report it rather than passing corrupt data to task accounts.
    """
    received = _integer(received_ms, "received_ms")
    if isinstance(message, (str, bytes)):
        try:
            message = json.loads(message)
        except (ValueError, UnicodeError) as exc:
            raise MarketDataError("invalid websocket JSON") from exc
    if not isinstance(message, dict):
        raise MarketDataError("websocket message must be an object")
    data = message.get("data", message)
    if not isinstance(data, dict):
        raise MarketDataError("websocket data must be an object")
    try:
        if data.get("e") == "aggTrade":
            return "quote", {
                "price": _decimal(data["p"], "price"),
                "timestamp_ms": _integer(data["T"], "timestamp_ms"),
                "event_time_ms": _integer(data["E"], "event_time_ms"),
                "trade_id": _integer(data["a"], "trade_id"),
                "received_ms": received,
                "source": "binance_ws",
            }
        if data.get("e") == "kline":
            kline = data["k"]
            if not isinstance(kline, dict) or type(kline.get("x")) is not bool:
                raise MarketDataError("kline close flag must be boolean")
            result = validate_candle({
                "open_time_ms": kline["t"], "close_time_ms": kline["T"],
                "open": kline["o"], "high": kline["h"], "low": kline["l"],
                "close": kline["c"], "volume": kline["v"],
            })
            interval = kline.get("i")
            if interval not in INTERVAL_MS:
                raise MarketDataError("unsupported websocket interval")
            if (result["open_time_ms"] % INTERVAL_MS[interval]
                    or result["close_time_ms"] != result["open_time_ms"] + INTERVAL_MS[interval] - 1):
                raise MarketDataError("websocket kline duration mismatch")
            result["received_ms"] = received
            result["event_time_ms"] = _integer(data["E"], "event_time_ms")
            result["source"] = "binance_ws"
            return ("bar" if kline["x"] else "partial"), result
    except (KeyError, TypeError) as exc:
        raise MarketDataError("incomplete websocket market event") from exc
    if "code" in data or "error" in data:
        raise MarketDataError("websocket error: {}".format(str(data)[:240]))
    return None


class BinancePublicClient:
    """Only public GET endpoints. Metadata is cached under one concurrent lock."""

    def __init__(self, timeout: float = 15):
        if not 0 < float(timeout) <= 120:
            raise ValueError("timeout must be between 0 and 120 seconds")
        self.timeout = float(timeout)
        self._symbols_cache = []  # type: List[Dict[str, Any]]
        self._symbols_expiry = 0.0
        self._cache_lock = threading.Lock()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = REST_URL + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": "my-quant-paper/1.0"})
        # Conservative klines cost covers every allowed limit, including warmup.
        weight = (20 if path == "/fapi/v1/aggTrades" else
                  1 if path in ("/fapi/v1/time", "/fapi/v1/exchangeInfo") else 10)
        _REQUEST_WEIGHT_BUDGET.acquire(weight)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise MarketDataError("public market response exceeds size limit")
            data = json.loads(raw)
        except urllib.error.HTTPError as exc:
            retry_message = ""
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    seconds = float(retry_after)
                    if not 0 < seconds < float("inf"):
                        raise ValueError("invalid Retry-After")
                except (TypeError, ValueError):
                    seconds = 60.0
                _REQUEST_WEIGHT_BUDGET.defer(seconds)
                retry_message = "; shared cooldown {}s".format(seconds)
            raise MarketDataError("Binance public HTTP {}: {}{}".format(
                exc.code, exc.reason, retry_message)) from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if isinstance(exc, MarketDataError):
                raise
            raise MarketDataError("Binance public request failed: {}".format(exc)) from exc
        if isinstance(data, dict) and "code" in data:
            raise MarketDataError("Binance public error: {}".format(data.get("msg", data["code"])))
        return data

    def server_time(self) -> int:
        data = self._get("/fapi/v1/time")
        if not isinstance(data, dict) or "serverTime" not in data:
            raise MarketDataError("missing Binance server time")
        return _integer(data["serverTime"], "serverTime")

    @staticmethod
    def _parse_symbol(item: Dict[str, Any]) -> Dict[str, Any]:
        try:
            filters = {row["filterType"]: row for row in item["filters"]}
            lot = filters["LOT_SIZE"]
            market_lot = filters.get("MARKET_LOT_SIZE", {})

            def lot_value(name: str) -> str:
                value = market_lot.get(name, "0")
                _decimal(value, name, allow_zero=True)
                return _decimal(lot[name] if Decimal(str(value)) == 0 else value, name)

            notional = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
            result = {
                "symbol": _symbol(item["symbol"]),
                "base_asset": str(item["baseAsset"]),
                "quote_asset": str(item["quoteAsset"]),
                "tick_size": _decimal(filters["PRICE_FILTER"]["tickSize"], "tickSize"),
                "qty_step": lot_value("stepSize"), "min_qty": lot_value("minQty"),
                "max_qty": lot_value("maxQty"),
                "min_notional": _decimal(notional.get("notional", notional.get("minNotional")),
                                         "min_notional", allow_zero=True),
            }
            if Decimal(result["max_qty"]) < Decimal(result["min_qty"]):
                raise MarketDataError("max quantity is below minimum")
            return result
        except (KeyError, TypeError) as exc:
            raise MarketDataError("incomplete Binance symbol filters") from exc

    def symbols(self) -> List[Dict[str, Any]]:
        with self._cache_lock:
            if time.monotonic() >= self._symbols_expiry:
                data = self._get("/fapi/v1/exchangeInfo")
                if not isinstance(data, dict) or not isinstance(data.get("symbols"), list):
                    raise MarketDataError("missing Binance symbol metadata")
                parsed = []
                for item in data["symbols"]:
                    if (not isinstance(item, dict) or item.get("contractType") != "PERPETUAL"
                            or item.get("status") != "TRADING" or item.get("quoteAsset") != "USDT"
                            or item.get("marginAsset") != "USDT"):
                        continue
                    try:
                        parsed.append(self._parse_symbol(item))
                    except MarketDataError as exc:
                        LOGGER.warning("Skipping malformed Binance symbol %s: %s", item.get("symbol"), exc)
                if not parsed:
                    raise MarketDataError("no usable trading USDT perpetual symbols")
                self._symbols_cache = sorted(parsed, key=lambda row: row["symbol"])
                self._symbols_expiry = time.monotonic() + 300
            return [dict(row) for row in self._symbols_cache]

    def filters(self, symbol: str) -> Dict[str, Any]:
        wanted = _symbol(symbol)
        for item in self.symbols():
            if item["symbol"] == wanted:
                return item
        raise MarketDataError("symbol is not a trading USDT perpetual: {}".format(wanted))

    def klines(self, symbol: str, interval: str, limit: int = 500,
               start_ms: Optional[int] = None, end_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        symbol = _symbol(symbol)
        if interval not in INTERVAL_MS:
            raise MarketDataError("unsupported candle interval")
        limit = _integer(limit, "limit")
        if not 1 <= limit <= 1500:
            raise MarketDataError("kline limit must be 1..1500")
        params = {"symbol": symbol, "interval": interval, "limit": limit}  # type: Dict[str, Any]
        if start_ms is not None:
            params["startTime"] = _integer(start_ms, "start_ms")
        if end_ms is not None:
            params["endTime"] = _integer(end_ms, "end_ms")
        if start_ms is not None and end_ms is not None and params["startTime"] > params["endTime"]:
            raise MarketDataError("start_ms must not exceed end_ms")
        data = self._get("/fapi/v1/klines", params)
        if not isinstance(data, list):
            raise MarketDataError("klines response must be an array")
        candles = [parse_kline(row) for row in data]
        previous = -1
        for candle in candles:
            opened = candle["open_time_ms"]
            if (opened <= previous or opened % INTERVAL_MS[interval]
                    or candle["close_time_ms"] != opened + INTERVAL_MS[interval] - 1):
                raise MarketDataError("unordered or misaligned Binance klines")
            previous = opened
        return candles

    def agg_trades(self, symbol: str, from_id: Optional[int] = None,
                   limit: int = 1000) -> List[Dict[str, Any]]:
        """Return real aggregate trades, never prices synthesized from OHLC."""
        params = {"symbol": _symbol(symbol), "limit": _integer(limit, "limit")}
        if not 1 <= params["limit"] <= 1000:
            raise MarketDataError("aggregate trade limit must be 1..1000")
        if from_id is not None:
            params["fromId"] = _integer(from_id, "from_id")
        data = self._get("/fapi/v1/aggTrades", params)
        if not isinstance(data, list):
            raise MarketDataError("aggregate trades response must be an array")
        received_ms = int(time.time() * 1000)
        quotes = []
        previous = -1
        try:
            for row in data:
                trade_id = _integer(row["a"], "trade_id")
                if trade_id <= previous:
                    raise MarketDataError("aggregate trades must be ordered and unique")
                timestamp_ms = _integer(row["T"], "timestamp_ms")
                quotes.append({"price": _decimal(row["p"], "price"),
                               "timestamp_ms": timestamp_ms, "event_time_ms": timestamp_ms,
                               "trade_id": trade_id, "received_ms": received_ms,
                               "source": "rest_agg_trades"})
                previous = trade_id
        except (KeyError, TypeError) as exc:
            raise MarketDataError("incomplete aggregate trade data") from exc
        return quotes


class MarketFeed:
    """A stoppable, reconnecting public trade+kline stream for one market pair."""

    def __init__(self, symbol: str, interval: str,
                 on_event: Callable[[str, Dict[str, Any]], None],
                 client: Optional[BinancePublicClient] = None):
        self.symbol = _symbol(symbol)
        if interval not in INTERVAL_MS:
            raise MarketDataError("unsupported candle interval")
        self.interval = interval
        self.client = client or BinancePublicClient()
        self.on_event = on_event
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None  # type: Optional[threading.Thread]
        self._socket = None  # type: Any
        self._has_connected = False

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name="market-{}-{}".format(self.symbol, self.interval))
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            socket = self._socket
            thread = self._thread
        if socket is not None:
            try:
                socket.close(timeout=1)
            except Exception:
                LOGGER.debug("Error closing public websocket", exc_info=True)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

    def _emit(self, kind: str, data: Dict[str, Any]) -> None:
        try:
            self.on_event(kind, data)
        except Exception:
            LOGGER.exception("Market callback failed for %s %s (%s)", self.symbol, self.interval, kind)

    def _connection(self, status: str, message: str, recovered: bool = False,
                    source: str = "binance_ws") -> None:
        self._emit("connection", {"status": status, "message": message,
                                  "received_ms": int(time.time() * 1000), "recovered": recovered,
                                  "source": source})

    def _run(self) -> None:
        socket = None
        try:
            self._connection("connecting", "正在订阅币安公开成交与K线行情")
            try:
                websocket = importlib.import_module("websocket")
                stream = urllib.parse.quote(self.symbol.lower(), safe="")
                url = WEBSOCKET_URL + "{}@aggTrade/{}@kline_{}".format(stream, stream, self.interval)
                socket = websocket.create_connection(url, timeout=min(self.client.timeout, 10),
                                                     enable_multithread=True)
                socket.settimeout(1)
                with self._lock:
                    self._socket = socket
                self._run_websocket(websocket, socket)
            except Exception as exc:
                if not self._stop.is_set():
                    LOGGER.warning("Public websocket unavailable for %s %s: %s", self.symbol, self.interval, exc)
                    self._connection("reconnecting", "WebSocket不可用，切换REST真实逐笔成交轮询：{}".format(
                        str(exc)[:200]), source="rest_agg_trades")
            finally:
                with self._lock:
                    self._socket = None
                if socket is not None:
                    try:
                        socket.close(timeout=1)
                    except Exception:
                        LOGGER.debug("Error releasing public websocket", exc_info=True)
            if not self._stop.is_set():
                self._run_rest()
        finally:
            self._connection("disconnected", "行情订阅已停止")

    def _run_websocket(self, websocket: Any, socket: Any) -> None:
        last_valid = last_ping = time.monotonic()
        awaiting_pong = None
        connected = False
        last_invalid_log = -10.0
        while not self._stop.is_set():
            now = time.monotonic()
            if awaiting_pong is not None and now - awaiting_pong > 10:
                raise MarketDataError("WebSocket pong timeout")
            if now - last_valid > (60 if connected else 10):
                raise MarketDataError("未收到有效WebSocket行情")
            if now - last_ping >= 20:
                socket.ping("paper-feed")
                last_ping = awaiting_pong = now
            try:
                opcode, raw = socket.recv_data(control_frame=True)
            except websocket.WebSocketTimeoutException:
                continue
            if opcode == websocket.ABNF.OPCODE_PONG:
                awaiting_pong = None
                continue
            if opcode == websocket.ABNF.OPCODE_PING:
                continue  # websocket-client has already sent the pong.
            if opcode == websocket.ABNF.OPCODE_CLOSE:
                raise MarketDataError("公开行情连接已关闭")
            if opcode != websocket.ABNF.OPCODE_TEXT:
                continue
            try:
                if len(raw) > 512 * 1024:
                    raise MarketDataError("websocket event exceeds size limit")
                payload = json.loads(raw)
                event_data = payload.get("data", payload) if isinstance(payload, dict) else None
                if isinstance(event_data, dict) and event_data.get("s", self.symbol) != self.symbol:
                    raise MarketDataError("websocket symbol mismatch")
                if (isinstance(event_data, dict) and event_data.get("e") == "kline"
                        and event_data.get("k", {}).get("i") != self.interval):
                    raise MarketDataError("websocket interval mismatch")
                event = map_message(payload, int(time.time() * 1000))
            except (MarketDataError, ValueError, UnicodeError, AttributeError) as exc:
                if now - last_invalid_log >= 10:
                    LOGGER.warning("Invalid %s %s websocket event: %s", self.symbol, self.interval, exc)
                    self._connection("connected" if connected else "connecting",
                                     "忽略无效行情：{}".format(str(exc)[:240]))
                    last_invalid_log = now
                continue
            if event is None:
                continue
            last_valid = time.monotonic()
            if not connected:
                connected = True
                self._connection("connected", "公开实时行情已连接", self._has_connected)
                self._has_connected = True
            self._emit(*event)

    def _rest_bars(self, server_ms: int) -> List[Tuple[str, Dict[str, Any]]]:
        candles = self.client.klines(self.symbol, self.interval, limit=2)
        received_ms = int(time.time() * 1000)
        result = []
        for candle in candles:
            candle = dict(candle, received_ms=received_ms, event_time_ms=server_ms, source="rest_klines")
            result.append(("bar" if candle["close_time_ms"] < server_ms else "partial", candle))
        return result

    def _run_rest(self) -> None:
        """Public polling with a minimum 5s interval, plus shared rate limits.

        On every recovery seed the latest trade without emitting its old price.
        Only subsequently fetched real trades may trigger account executions.
        """
        last_id = None
        retry_delay = 1.0
        while not self._stop.is_set():
            try:
                if last_id is None:
                    seed = self.client.agg_trades(self.symbol, limit=1)
                    if not seed:
                        raise MarketDataError("尚无真实逐笔成交，等待行情")
                    server_ms = self.client.server_time()
                    bars = self._rest_bars(server_ms)
                    if self._stop.is_set():
                        break
                    last_id = seed[-1]["trade_id"]
                    self._connection("connected", "REST真实逐笔成交轮询（至少5秒，按公开接口限流调整）；重连旧价不补成交",
                                     self._has_connected, source="rest_agg_trades")
                    self._has_connected = True
                    for event in bars:
                        self._emit(*event)
                else:
                    quotes = []
                    cursor = last_id + 1
                    for page in range(5):
                        batch = self.client.agg_trades(self.symbol, from_id=cursor)
                        for quote in batch:
                            if quote["trade_id"] != cursor:
                                raise MarketDataError("真实成交ID缺口：预期{}，收到{}".format(
                                    cursor, quote["trade_id"]))
                            quotes.append(quote)
                            cursor += 1
                        if len(batch) < 1000:
                            break
                    else:
                        raise MarketDataError("逐笔成交积压超过5000笔，标记缺口后重新同步")
                    server_ms = self.client.server_time()
                    bars = self._rest_bars(server_ms)
                    if self._stop.is_set():
                        break
                    for quote in quotes:
                        if self._stop.is_set():
                            break
                        self._emit("quote", quote)
                    last_id = cursor - 1
                    for event in bars:
                        if self._stop.is_set():
                            break
                        self._emit(*event)
                retry_delay = 1.0
                if self._stop.wait(5):
                    break
            except Exception as exc:
                if self._stop.is_set():
                    break
                LOGGER.warning("REST market stream %s %s failed: %s", self.symbol, self.interval, exc)
                self._connection("reconnecting", "REST行情缺口，{}秒后重新同步；旧价不补成交：{}".format(
                    int(retry_delay), str(exc)[:200]), source="rest_agg_trades")
                last_id = None
                if self._stop.wait(retry_delay):
                    break
                retry_delay = min(30.0, retry_delay * 2)
