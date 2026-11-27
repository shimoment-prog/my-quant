"""Transactional SQLite persistence. Every account and event belongs to a task."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, document TEXT NOT NULL, state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategies (
                id TEXT NOT NULL, version INTEGER NOT NULL, document TEXT NOT NULL,
                PRIMARY KEY (id, version)
            );
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                time_ms INTEGER NOT NULL, type TEXT NOT NULL,
                message TEXT NOT NULL, data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS logs_task ON logs(task_id, id);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS candles (
                task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                open_time_ms INTEGER NOT NULL, document TEXT NOT NULL,
                PRIMARY KEY(task_id,open_time_ms)
            );
        """)
        self.db.commit()

    def load_tasks(self):
        with self.lock:
            return [(json.loads(doc), json.loads(state)) for doc, state in
                    self.db.execute("SELECT document,state FROM tasks ORDER BY rowid")]

    def save(self, task, state, events=(), candles=()):
        # Snapshot + fills + account state + log events commit together.
        with self.lock, self.db:
            self.db.execute("INSERT INTO tasks VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET "
                            "document=excluded.document,state=excluded.state",
                            (task["id"], dumps(task), dumps(state)))
            self.db.executemany("INSERT INTO logs(task_id,time_ms,type,message,data) VALUES(?,?,?,?,?)",
                                [(task["id"], int(e.get("time_ms", 0)), e.get("type", "info"),
                                  str(e.get("message", "")), dumps(e.get("data", {}))) for e in events])
            self.db.executemany("INSERT INTO candles VALUES(?,?,?) ON CONFLICT(task_id,open_time_ms) "
                                "DO UPDATE SET document=excluded.document",
                                [(task["id"], b["open_time_ms"], dumps(b)) for b in candles])

    def candles(self, identifier, before=None, around=None, limit=500):
        limit = min(1500, max(2, int(limit)))
        with self.lock:
            if around is not None:
                older = self.db.execute("SELECT document FROM candles WHERE task_id=? AND open_time_ms<? "
                    "ORDER BY open_time_ms DESC LIMIT ?", (identifier, around * 1000, limit // 2)).fetchall()
                newer = self.db.execute("SELECT document FROM candles WHERE task_id=? AND open_time_ms>=? "
                    "ORDER BY open_time_ms ASC LIMIT ?", (identifier, around * 1000, limit - len(older))).fetchall()
                bars = [json.loads(r[0]) for r in reversed(older)] + [json.loads(r[0]) for r in newer]
            else:
                boundary = (before * 1000) if before is not None else 9223372036854775807
                rows = self.db.execute("SELECT document FROM candles WHERE task_id=? AND open_time_ms<? "
                    "ORDER BY open_time_ms DESC LIMIT ?", (identifier, boundary, limit)).fetchall()
                bars = [json.loads(r[0]) for r in reversed(rows)]
            more = bool(bars and self.db.execute("SELECT 1 FROM candles WHERE task_id=? AND open_time_ms<? LIMIT 1",
                                                (identifier, bars[0]["open_time_ms"])).fetchone())
        return bars, more

    def logs(self, identifier, limit=150):
        with self.lock:
            rows = self.db.execute("SELECT id,time_ms,type,message,data FROM logs WHERE task_id=? "
                                   "ORDER BY id DESC LIMIT ?", (identifier, min(1000, limit))).fetchall()
        return [dict(id=r[0], time_ms=r[1], type=r[2], message=r[3], data=json.loads(r[4])) for r in rows]

    def manual_pause_intent(self, identifier):
        """Infer legacy user intent from the full log, never a truncated page."""
        with self.lock:
            row = self.db.execute("SELECT type FROM logs WHERE task_id=? AND type IN ('paused','resumed') "
                                  "ORDER BY id DESC LIMIT 1", (identifier,)).fetchone()
            if row:
                return row[0] == "paused"
            known = self.db.execute("SELECT 1 FROM logs WHERE task_id=? AND type IN "
                                   "('task_created','ready','connection','data_gap','restored') LIMIT 1",
                                   (identifier,)).fetchone()
        return False if known else None

    def delete(self, identifier):
        with self.lock, self.db:
            self.db.execute("DELETE FROM tasks WHERE id=?", (identifier,))

    def strategies(self):
        with self.lock:
            rows = self.db.execute("SELECT s.document FROM strategies s JOIN "
                                   "(SELECT id,MAX(version) v FROM strategies GROUP BY id) x "
                                   "ON s.id=x.id AND s.version=x.v ORDER BY s.rowid").fetchall()
        return [json.loads(r[0]) for r in rows]

    def strategy(self, identifier, version=None):
        with self.lock:
            if version is None:
                row = self.db.execute("SELECT document FROM strategies WHERE id=? ORDER BY version DESC LIMIT 1",
                                      (identifier,)).fetchone()
            else:
                row = self.db.execute("SELECT document FROM strategies WHERE id=? AND version=?",
                                      (identifier, int(version))).fetchone()
        if not row:
            raise ValueError("策略版本不存在")
        return json.loads(row[0])

    def save_strategy(self, item):
        with self.lock, self.db:
            self.db.execute("INSERT INTO strategies VALUES(?,?,?)",
                            (item["id"], int(item["version"]), dumps(item)))

    def get_setting(self, key, default=None):
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self.lock, self.db:
            self.db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                            (key, dumps(value)))

    def close(self):
        with self.lock:
            self.db.close()
