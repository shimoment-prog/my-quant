#!/usr/bin/env python3
"""Run the local paper-trading web application (public Binance data only)."""
from __future__ import annotations

import argparse
import csv
import io
import json
import signal
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__:
    from .backend.engine import INTERVAL_MS
    from .backend.service import DEFAULT_ACCOUNT, Manager
    from .backend.storage import Store
else:
    from backend.engine import INTERVAL_MS
    from backend.service import DEFAULT_ACCOUNT, Manager
    from backend.storage import Store

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
VERSION = "0.1.4"


def handler_for(manager, port):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            # Avoid per-second API polling noise; keep actual failures visible.
            if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
                super().log_message(fmt, *args)

        def _send(self, data, status=200, mime="application/json; charset=utf-8", headers=None):
            if isinstance(data, (dict, list)):
                data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            elif isinstance(data, str):
                data = data.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                             "connect-src 'self'; img-src 'self' data:; frame-ancestors 'self'; base-uri 'self'")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _check_origin(self):
            actual_port = self.server.server_address[1]
            host = self.headers.get("Host", "")
            if host not in {"localhost:%d" % actual_port, "127.0.0.1:%d" % actual_port, "[::1]:%d" % actual_port}:
                raise PermissionError("仅允许从本机地址访问")
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + host:
                raise PermissionError("不接受跨站点请求")
            if self.command not in {"GET", "HEAD"} and self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise PermissionError("不接受跨站点修改")

        def _body(self):
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("请使用JSON格式提交")
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                raise ValueError("无效请求长度")
            if not 0 < length <= 262144:
                raise ValueError("请求为空或超过256KB")
            def reject_constant(value):
                raise ValueError("JSON不能包含非有限数值")
            try:
                body = json.loads(self.rfile.read(length), parse_constant=reject_constant)
            except (json.JSONDecodeError, UnicodeError):
                raise ValueError("JSON格式错误")
            if not isinstance(body, dict):
                raise ValueError("请求内容需要是对象")
            return body

        def _dispatch(self):
            self._check_origin()
            path = urllib.parse.urlsplit(self.path).path
            parts = path.strip("/").split("/")
            if self.command == "GET":
                if path == "/api/bootstrap":
                    return self._send({"app": {"name": "模拟交易", "version": VERSION,
                        "execution_note": "公开实时成交价驱动模拟；收盘信号后等待下一可用价格成交；未计资金费、标记价及强平。"},
                        "intervals": list(INTERVAL_MS), "strategies": manager.strategies(),
                        "tasks": manager.list_tasks(), "market": manager.market,
                        "defaults": {"account": DEFAULT_ACCOUNT}})
                if path == "/api/tasks":
                    return self._send({"tasks": manager.list_tasks()})
                if path == "/api/market":
                    return self._send(manager.market)
                if path == "/api/health":
                    return self._send({"status": "ok", "version": VERSION, "market": manager.market["status"]})
                if len(parts) >= 3 and parts[:2] == ["api", "tasks"]:
                    if len(parts) == 4 and parts[3] == "chart":
                        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                        options = {key: int(query[key][0]) for key in ("before", "around", "limit") if key in query}
                        if any(v < 0 for v in options.values()):
                            raise ValueError("图表时间和数量须为非负整数")
                        return self._send(manager.chart(parts[2], **options))
                    detail = manager.detail(parts[2])
                    if len(parts) == 3:
                        return self._send(detail)
                    if len(parts) == 4 and parts[3] == "trades.csv":
                        columns = ["id", "side", "status", "signal_time_ms", "entry_time_ms", "entry_reference", "entry_fill",
                                   "quantity", "entry_notional", "margin_used", "initial_stop", "stop", "target", "activation_level",
                                   "exit_time_ms", "exit_fill", "exit_reason", "entry_fee", "exit_fee", "gross_pnl", "net_pnl", "balance_after"]
                        stream = io.StringIO()
                        stream.write("\ufeff")
                        writer = csv.DictWriter(stream, columns, extrasaction="ignore")
                        writer.writeheader()
                        writer.writerows(detail["trades"])
                        return self._send(stream.getvalue(), mime="text/csv; charset=utf-8",
                            headers={"Content-Disposition": 'attachment; filename="trades-%s.csv"' % parts[2]})
                files = {"/": ROOT / "frontend/index.html", "/assets/app.js": ROOT / "frontend/app.js",
                         "/assets/styles.css": ROOT / "frontend/styles.css",
                         "/vendor/lightweight-charts.js": REPOSITORY / "strategy/ema_ma_rsi_key_candle/chart_assets/lightweight-charts-4.2.3.js"}
                if path in files and files[path].is_file():
                    mime = "text/html; charset=utf-8" if path == "/" else "text/css; charset=utf-8" if path.endswith("css") else "text/javascript; charset=utf-8"
                    return self._send(files[path].read_bytes(), mime=mime)
            elif self.command == "POST":
                body = self._body()
                if path == "/api/tasks":
                    return self._send(manager.create(body), 201)
                if path == "/api/strategies":
                    return self._send(manager.save_strategy(body), 201)
                if path == "/api/market/refresh":
                    threading.Thread(target=manager.refresh_market, daemon=True).start()
                    return self._send({"status": "refreshing"})
                if len(parts) == 4 and parts[:2] == ["api", "tasks"]:
                    if parts[3] == "action":
                        return self._send(manager.action(parts[2], body.get("action")))
                    if parts[3] == "copy":
                        return self._send(manager.copy_task(parts[2], body), 201)
                if len(parts) == 3 and parts[:2] == ["api", "strategies"]:
                    return self._send(manager.save_strategy(body, parts[2]), 201)
            elif self.command == "PUT":
                if len(parts) == 3 and parts[:2] == ["api", "tasks"]:
                    return self._send(manager.update(parts[2], self._body()))
            elif self.command == "DELETE":
                if len(parts) == 3 and parts[:2] == ["api", "tasks"]:
                    manager.delete(parts[2])
                    return self._send({"deleted": True})
            self._send({"error": "接口或资源不存在"}, 404)

        def do_GET(self):
            self._run()

        def do_POST(self):
            self._run()

        def do_PUT(self):
            self._run()

        def do_DELETE(self):
            self._run()

        def _run(self):
            try:
                self._dispatch()
            except PermissionError as exc:
                self._send({"error": str(exc)}, 403)
            except KeyError as exc:
                self._send({"error": str(exc.args[0])}, 404)
            except (ValueError, TypeError) as exc:
                self._send({"error": str(exc)}, 400)
            except Exception as exc:
                self.log_error("request failed: %s", exc)
                self._send({"error": "后台处理失败，请查看运行终端"}, 500)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--runtime", type=Path, default=ROOT / "runtime")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    args.runtime.mkdir(parents=True, exist_ok=True)
    # Prevent a second process from trading the same simulated accounts.
    import fcntl
    lock_file = (args.runtime / "server.lock").open("a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("此runtime目录已有后台运行，请使用原服务或指定另一runtime目录")
    store = Store(args.runtime / "paper.sqlite3")
    manager = Manager(store)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(manager, args.port))
    httpd.daemon_threads = True
    def stop(_signal, _frame):
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("模拟交易网页：http://127.0.0.1:%d" % args.port, flush=True)
    print("数据目录：%s；仅模拟，不接入交易账户。" % args.runtime.resolve(), flush=True)
    try:
        httpd.serve_forever(poll_interval=.5)
    finally:
        httpd.server_close()
        manager.shutdown()
        store.close()
        lock_file.close()


if __name__ == "__main__":
    main()
