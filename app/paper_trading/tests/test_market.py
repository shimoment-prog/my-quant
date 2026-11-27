"""Offline public-market protocol and lifecycle checks (no account or orders)."""
import io
import json
import threading
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from app.paper_trading.backend.market import (
    BinancePublicClient, INTERVALS, MarketDataError, MarketFeed, map_message,
    parse_kline, validate_candle, _RequestWeightBudget,
)


MODULE = "app.paper_trading.backend.market"
ROW = [0, "100.00", "105.00", "99.00", "102.00", "5.5", 59999]


def kline_message(closed=False):
    return {"stream": "btcusdt@kline_1m", "data": {
        "e": "kline", "E": 60000, "s": "BTCUSDT", "k": {
            "t": 0, "T": 59999, "s": "BTCUSDT", "i": "1m", "o": "100.00",
            "h": "105.00", "l": "99.00", "c": "102.00", "v": "5.5", "x": closed,
        }}}


def quote_message(price="101.2", trade_id=24):
    return {"stream": "btcusdt@aggTrade", "data": {
        "e": "aggTrade", "E": 60000, "s": "BTCUSDT", "p": price,
        "a": trade_id, "T": 59998}}


def symbol_info(symbol="BTCUSDT", tick="0.10", step="0.001"):
    return {"symbol": symbol, "baseAsset": symbol[:-4], "quoteAsset": "USDT",
            "marginAsset": "USDT", "contractType": "PERPETUAL", "status": "TRADING",
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": tick},
                {"filterType": "LOT_SIZE", "stepSize": "0.01", "minQty": "0.01", "maxQty": "1000"},
                {"filterType": "MARKET_LOT_SIZE", "stepSize": step, "minQty": "0.001", "maxQty": "120"},
                {"filterType": "MIN_NOTIONAL", "notional": "50"},
            ]}


class CandleTests(unittest.TestCase):
    def test_candle_price_precision_and_last_millisecond_are_preserved(self):
        self.assertEqual(parse_kline(ROW), {
            "open_time_ms": 0, "close_time_ms": 59999, "open": "100.00", "high": "105.00",
            "low": "99.00", "close": "102.00", "volume": "5.5"})

    def test_nonfinite_nonpositive_prices_and_bad_volume_are_rejected(self):
        for field, values in {
            "open": ["NaN", "Infinity", "-Infinity", "0", "-1", True, None],
            "volume": ["NaN", "Infinity", "-1", True],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    candle = parse_kline(ROW)
                    candle[field] = value
                    with self.assertRaises(MarketDataError):
                        validate_candle(candle)
        candle = parse_kline(ROW)
        candle["volume"] = "0"
        self.assertEqual(validate_candle(candle)["volume"], "0")

    def test_impossible_ohlc_times_and_incomplete_arrays_are_rejected(self):
        for field, value in [("high", "101"), ("low", "101"),
                             ("close_time_ms", 0), ("open_time_ms", -1),
                             ("open_time_ms", 0.5), ("close_time_ms", True)]:
            with self.subTest(field=field):
                candle = parse_kline(ROW)
                candle[field] = value
                with self.assertRaises(MarketDataError):
                    validate_candle(candle)
        for row in [None, {}, ROW[:6]]:
            with self.assertRaises(MarketDataError):
                parse_kline(row)


class MessageTests(unittest.TestCase):
    def test_only_explicit_true_is_a_closed_bar(self):
        kind, partial = map_message(kline_message(False), 61000)
        self.assertEqual(kind, "partial")
        kind, closed = map_message(json.dumps(kline_message(True)), 62000)
        self.assertEqual(kind, "bar")
        self.assertEqual(closed["close_time_ms"], 59999)
        self.assertEqual(closed["received_ms"], 62000)
        self.assertEqual(closed["event_time_ms"], 60000)
        self.assertEqual(partial["close"], closed["close"])
        for value in ["true", 1, None]:
            message = kline_message()
            message["data"]["k"]["x"] = value
            with self.assertRaises(MarketDataError):
                map_message(message, 62000)

    def test_aggregate_trade_uses_trade_time_id_and_observed_price(self):
        kind, quote = map_message(quote_message(), 60001)
        self.assertEqual(kind, "quote")
        self.assertEqual(quote, {"price": "101.2", "timestamp_ms": 59998,
                                 "event_time_ms": 60000, "trade_id": 24, "received_ms": 60001,
                                 "source": "binance_ws"})
        for key, value in [("p", "NaN"), ("p", 0), ("T", -1), ("E", -1), ("a", True)]:
            message = quote_message()
            message["data"][key] = value
            with self.assertRaises(MarketDataError):
                map_message(message, 60001)

    def test_interval_duration_malformed_payloads_and_error_are_rejected(self):
        for mutation in [("T", 60000), ("i", "2w")]:
            message = kline_message()
            message["data"]["k"][mutation[0]] = mutation[1]
            with self.assertRaises(MarketDataError):
                map_message(message, 60001)
        for data in ["not JSON", "[]", {"data": []}, {"code": -1121, "msg": "bad symbol"}]:
            with self.assertRaises(MarketDataError):
                map_message(data, 60001)
        self.assertIsNone(map_message({"result": None, "id": 1}, 60001))


class RequestBudgetTests(unittest.TestCase):
    def test_rolling_weight_window_waits_without_exceeding_allowance(self):
        now, waits = [0.0], []

        def advance(delay):
            waits.append(delay)
            now[0] += delay

        budget = _RequestWeightBudget(30, 60, lambda: now[0], advance)
        budget.acquire(20)
        now[0] = 5
        budget.acquire(10)
        budget.acquire(1)
        self.assertEqual(now[0], 60)
        self.assertEqual(budget._used, 11)
        self.assertTrue(waits)
        self.assertTrue(all(0 < delay <= 1 for delay in waits))
        with self.assertRaises(ValueError):
            budget.acquire(31)

    def test_exchange_cooldown_applies_to_the_whole_shared_budget(self):
        now, waits = [10.0], []

        def advance(delay):
            waits.append(delay)
            now[0] += delay

        budget = _RequestWeightBudget(100, 60, lambda: now[0], advance)
        budget.acquire(1)
        budget.defer(7)
        budget.acquire(1)
        self.assertEqual(now[0], 17)
        self.assertEqual(sum(waits), 7)

    def test_clients_share_one_budget_with_conservative_endpoint_weights(self):
        first, second = BinancePublicClient(), BinancePublicClient()
        budget = unittest.mock.Mock()
        with patch(MODULE + "._REQUEST_WEIGHT_BUDGET", budget), \
                patch(MODULE + ".urllib.request.urlopen", side_effect=lambda *a, **k: io.BytesIO(b'[]')):
            first._get("/fapi/v1/aggTrades", {"limit": 1000})
            second._get("/fapi/v1/time")
            first._get("/fapi/v1/exchangeInfo")
            second._get("/fapi/v1/klines", {"limit": 2})
            first._get("/fapi/v1/klines", {"limit": 1500})
        self.assertEqual(budget.acquire.call_args_list, [unittest.mock.call(weight)
                                                       for weight in [20, 1, 1, 10, 10]])

    def test_http_429_is_charged_reported_and_honors_retry_after(self):
        budget = unittest.mock.Mock()
        error = urllib.error.HTTPError("https://fapi.binance.com/fapi/v1/time", 429,
                                       "Too Many Requests", {"Retry-After": "7"}, None)
        with patch(MODULE + "._REQUEST_WEIGHT_BUDGET", budget), \
                patch(MODULE + ".urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(MarketDataError, "HTTP 429.*shared cooldown 7"):
                BinancePublicClient().server_time()
        budget.acquire.assert_called_once_with(1)
        budget.defer.assert_called_once_with(7)


class RestTests(unittest.TestCase):
    def setUp(self):
        self.client = BinancePublicClient()

    def test_symbols_filter_and_per_symbol_market_lot_values(self):
        btc, eth = symbol_info(), symbol_info("ETHUSDT", "0.01", "0.002")
        eth["filters"][2]["minQty"] = "0"
        eth["filters"][2]["maxQty"] = "0"
        disabled = symbol_info("OLDUSDT")
        disabled["status"] = "SETTLING"
        coin_margin = symbol_info("OTHERUSDT")
        coin_margin["marginAsset"] = "OTHER"
        with patch.object(self.client, "_get", return_value={"symbols": [btc, eth, disabled, coin_margin]}):
            symbols = self.client.symbols()
            self.assertEqual([row["symbol"] for row in symbols], ["BTCUSDT", "ETHUSDT"])
            self.assertEqual(symbols[0]["tick_size"], "0.10")
            self.assertEqual(symbols[0]["max_qty"], "120")
            self.assertEqual(symbols[1]["qty_step"], "0.002")
            self.assertEqual(symbols[1]["min_qty"], "0.01")
            self.assertEqual(symbols[1]["max_qty"], "1000")
            self.assertEqual(self.client.filters("ETHUSDT")["tick_size"], "0.01")
            with self.assertRaises(MarketDataError):
                self.client.filters("OLDUSDT")

    def test_metadata_cache_is_concurrent_defensive_and_expires(self):
        clock = [10.0]
        with patch(MODULE + ".time.monotonic", side_effect=lambda: clock[0]), \
                patch.object(self.client, "_get", return_value={"symbols": [symbol_info()]}) as get:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: self.client.symbols(), range(16)))
            self.assertEqual(get.call_count, 1)
            results[0][0]["tick_size"] = "999"
            self.assertEqual(self.client.filters("BTCUSDT")["tick_size"], "0.10")
            clock[0] = 311
            self.client.symbols()
            self.assertEqual(get.call_count, 2)

    def test_server_time_is_separate_and_klines_can_include_unclosed_bar(self):
        with patch.object(self.client, "_get", return_value={"serverTime": 60000}) as get:
            self.assertEqual(self.client.server_time(), 60000)
            get.assert_called_once_with("/fapi/v1/time")
        next_row = [60000] + ROW[1:6] + [119999]
        with patch.object(self.client, "_get", return_value=[ROW, next_row]) as get:
            result = self.client.klines("BTCUSDT", "1m", 2, 0, 120000)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[-1]["close_time_ms"], 119999)
            get.assert_called_once_with("/fapi/v1/klines", {
                "symbol": "BTCUSDT", "interval": "1m", "limit": 2,
                "startTime": 0, "endTime": 120000})

    def test_rest_rejects_duplicate_or_misaligned_bars_and_bad_queries(self):
        for rows in [[ROW, ROW], [[1] + ROW[1:]]]:
            with patch.object(self.client, "_get", return_value=rows):
                with self.assertRaises(MarketDataError):
                    self.client.klines("BTCUSDT", "1m")
        for args in [("BTC/USDT", "1m", 5), ("BTCUSDT", "2w", 5),
                     ("BTCUSDT", "1m", 0), ("BTCUSDT", "1m", 1501)]:
            with self.assertRaises(MarketDataError):
                self.client.klines(*args)
        with self.assertRaises(MarketDataError):
            self.client.klines("BTCUSDT", "1m", start_ms=2, end_ms=1)

    def test_transport_is_public_get_with_bounded_timeout(self):
        with patch(MODULE + ".urllib.request.urlopen", return_value=io.BytesIO(b'{"serverTime":123}')) as opened:
            self.assertEqual(self.client.server_time(), 123)
        request = opened.call_args[0][0]
        self.assertEqual(request.full_url, "https://fapi.binance.com/fapi/v1/time")
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.get_header("X-mbx-apikey"))
        self.assertEqual(opened.call_args[1]["timeout"], 15)

    def test_aggregate_trades_keep_real_price_time_and_request_cursor(self):
        raw = [{"a": 100, "p": "100.01", "T": 65000}, {"a": 101, "p": "99.95", "T": 65001}]
        with patch.object(self.client, "_get", return_value=raw) as get:
            quotes = self.client.agg_trades("BTCUSDT", from_id=100, limit=500)
        get.assert_called_once_with("/fapi/v1/aggTrades", {"symbol": "BTCUSDT", "fromId": 100, "limit": 500})
        self.assertEqual([row["price"] for row in quotes], ["100.01", "99.95"])
        self.assertEqual(quotes[0]["timestamp_ms"], quotes[0]["event_time_ms"])
        self.assertEqual(quotes[0]["source"], "rest_agg_trades")
        for rows in [[raw[0], raw[0]], [{"a": 1, "p": "NaN", "T": 1}], [{"a": True, "p": "1", "T": 1}]]:
            with patch.object(self.client, "_get", return_value=rows):
                with self.assertRaises(MarketDataError):
                    self.client.agg_trades("BTCUSDT")

    def test_unicode_binance_symbols_are_encoded_as_query_parameters(self):
        info = symbol_info("币安人生USDT")
        with patch.object(self.client, "_get", return_value={"symbols": [info]}):
            self.assertEqual(self.client.symbols()[0]["symbol"], "币安人生USDT")


class ImmediateEvent:
    """A real stop flag, with retry waits recorded rather than slept in tests."""
    def __init__(self):
        self.flag = threading.Event()
        self.waits = []

    def set(self):
        self.flag.set()

    def clear(self):
        self.flag.clear()

    def is_set(self):
        return self.flag.is_set()

    def wait(self, timeout):
        self.waits.append(timeout)
        return self.flag.is_set()


class FakeSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.closed = False
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv_data(self, control_frame=False):
        item = next(self.messages)
        if isinstance(item, Exception):
            raise item
        return 1, json.dumps(item)

    def close(self, timeout=None):
        self.closed = True


def fake_websocket(create_connection):
    return SimpleNamespace(create_connection=create_connection, WebSocketTimeoutException=TimeoutError,
                           ABNF=SimpleNamespace(OPCODE_TEXT=1, OPCODE_CLOSE=8, OPCODE_PING=9, OPCODE_PONG=10))


def rest_quote(trade_id, price="101", timestamp=65000):
    return {"price": price, "trade_id": trade_id, "timestamp_ms": timestamp,
            "event_time_ms": timestamp, "received_ms": 66000, "source": "rest_agg_trades"}


def rest_client(batches):
    return SimpleNamespace(timeout=15, agg_trades=unittest.mock.Mock(side_effect=batches),
                           server_time=unittest.mock.Mock(return_value=60000),
                           klines=unittest.mock.Mock(return_value=[parse_kline(ROW),
                               parse_kline([60000] + ROW[1:6] + [119999])]))


class FeedTests(unittest.TestCase):
    def test_feed_closed_partial_invalid_data_and_stop_close(self):
        events = []
        feed = None

        def receive(kind, data):
            events.append((kind, data))
            if kind == "bar":
                feed.stop()

        feed = MarketFeed("BTCUSDT", "1m", receive)
        socket = FakeSocket([quote_message(), quote_message("NaN"), kline_message(), kline_message(True)])
        create = unittest.mock.Mock(return_value=socket)
        with patch(MODULE + ".importlib.import_module", return_value=fake_websocket(create)):
            feed._run()
        self.assertEqual([kind for kind, _ in events if kind != "connection"], ["quote", "partial", "bar"])
        self.assertTrue(socket.closed)
        self.assertEqual(socket.timeout, 1)
        self.assertTrue(any("忽略无效行情" in data["message"] for kind, data in events if kind == "connection"))
        self.assertEqual(events[-1][1]["status"], "disconnected")
        self.assertIn("btcusdt@aggTrade/btcusdt@kline_1m", create.call_args[0][0])

    def test_websocket_failure_falls_back_to_real_trades_and_reports_recovery(self):
        events = []
        socket = FakeSocket([quote_message(), OSError("dropped")])
        client = rest_client([[rest_quote(100)], [rest_quote(101)]])
        feed = None

        def receive(kind, data):
            events.append((kind, data))
            if kind == "quote" and data["trade_id"] == 101:
                feed.stop()

        feed = MarketFeed("BTCUSDT", "1m", receive, client)
        feed._stop = ImmediateEvent()
        create = unittest.mock.Mock(return_value=socket)
        with patch(MODULE + ".importlib.import_module", return_value=fake_websocket(create)):
            feed._run()
        connected = [data for kind, data in events if kind == "connection" and data["status"] == "connected"]
        self.assertEqual([data["recovered"] for data in connected], [False, True])
        self.assertEqual([data["source"] for data in connected], ["binance_ws", "rest_agg_trades"])
        self.assertEqual([data["trade_id"] for kind, data in events if kind == "quote"], [24, 101])
        self.assertTrue(socket.closed)
        self.assertEqual(create.call_count, 1)
        self.assertTrue(any(data["status"] == "reconnecting" for kind, data in events if kind == "connection"))

    def test_repeated_rest_failure_has_bounded_backoff_and_stoppable_thread(self):
        attempts = []
        client = rest_client([])
        feed = MarketFeed("BTCUSDT", "1m", lambda *_: None, client)
        feed._stop = ImmediateEvent()

        def fail(*args, **kwargs):
            attempts.append(args)
            if len(attempts) == 8:
                feed._stop.set()
            raise OSError("offline")

        client.agg_trades.side_effect = fail
        with patch(MODULE + ".importlib.import_module", return_value=fake_websocket(
                unittest.mock.Mock(side_effect=OSError("offline")))):
            feed.start()
            feed._thread.join(timeout=2)
            feed.stop()
        self.assertFalse(feed._thread.is_alive())
        self.assertTrue(feed._thread.daemon)
        self.assertEqual(feed._stop.waits, [1, 2, 4, 8, 16, 30, 30])

    def test_missing_websocket_dependency_uses_only_real_trade_fallback(self):
        events = []
        client = BinancePublicClient()
        feed = MarketFeed("BTCUSDT", "1m", lambda *event: events.append(event), client)
        with patch(MODULE + ".importlib.import_module", side_effect=ImportError("websocket-client")), \
                patch.object(feed, "_run_rest") as fallback:
            feed._run()
        fallback.assert_called_once_with()
        self.assertEqual(events[-1][1]["status"], "disconnected")
        self.assertTrue(any("websocket-client" in data["message"] for _, data in events))

    def test_rest_gap_discards_old_prices_reseeds_and_keeps_bar_types(self):
        events = []
        client = rest_client([[rest_quote(10)], [rest_quote(12)], [rest_quote(50)], [rest_quote(51)]])
        feed = None

        def receive(kind, data):
            events.append((kind, data))
            if kind == "quote":
                feed.stop()

        feed = MarketFeed("BTCUSDT", "1m", receive, client)
        feed._stop = ImmediateEvent()
        feed._run_rest()
        self.assertEqual([data["trade_id"] for kind, data in events if kind == "quote"], [51])
        self.assertTrue(any("ID缺口" in data["message"] for kind, data in events if kind == "connection"))
        self.assertEqual([kind for kind, _ in events if kind in ("bar", "partial")],
                         ["bar", "partial", "bar", "partial"])
        self.assertTrue(all(data["event_time_ms"] == 60000 for kind, data in events if kind in ("bar", "partial")))
        self.assertEqual(client.agg_trades.call_args_list, [
            unittest.mock.call("BTCUSDT", limit=1), unittest.mock.call("BTCUSDT", from_id=11),
            unittest.mock.call("BTCUSDT", limit=1), unittest.mock.call("BTCUSDT", from_id=51)])


if __name__ == "__main__":
    unittest.main()
