"""Адаптер хранилища на SQLite (встроен в Python)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from core import ROOT
from core.event import Event
from core.storage import Run, Storage

MIGRATIONS = ROOT / "migrations"


def _ms(t: datetime) -> int:
    return int(t.timestamp() * 1000)


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def migrate(conn: sqlite3.Connection, folder: Path = MIGRATIONS) -> list[str]:
    """Применить ещё не применённые скрипты migrations/NNN_*.sql по порядку."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                 "(name TEXT PRIMARY KEY, applied_ms INTEGER NOT NULL)")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for path in sorted(folder.glob("*.sql")):
        if path.name in done:
            continue
        # Одна миграция — одна транзакция: либо целиком, либо никак (вместе с CREATE/ALTER).
        old, conn.isolation_level = conn.isolation_level, None
        try:
            conn.execute("BEGIN")
            for stmt in path.read_text().split(";"):
                if stmt.strip():
                    conn.execute(stmt)
            conn.execute("INSERT INTO schema_migrations VALUES (?, ?)",
                         (path.name, _ms(datetime.now(timezone.utc))))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.isolation_level = old
        applied.append(path.name)
    return applied


class SQLiteStorage(Storage):
    def __init__(self, path: str | Path = ROOT / "data" / "sistema.db"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        migrate(self.conn)

    def save(self, events: Iterable[Event]) -> list[Event]:
        now = _ms(datetime.now(timezone.utc))
        new = []
        with self.conn:
            for e in events:
                cur = self.conn.execute(
                    "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?)",
                    (e.id, e.schema_version, e.trace_id, e.source, e.kind, e.entity,
                     _ms(e.time), now, json.dumps(e.to_dict(), ensure_ascii=False)))
                if cur.rowcount:
                    new.append(e)
        return new

    def query(self, since=None, until=None, source=None, kind=None, limit=None):
        sql, args = "SELECT data, time_ms, id FROM events WHERE 1=1", []
        if since is not None:
            sql += " AND time_ms >= ?"; args.append(_ms(since))
        if until is not None:
            sql += " AND time_ms < ?"; args.append(_ms(until))
        if source is not None:
            sql += " AND source = ?"; args.append(source)
        if kind is not None:
            sql += " AND kind = ?"; args.append(kind)
        if limit is not None:
            # последние limit штук, но отдаём всё равно от старых к новым
            sql = f"SELECT * FROM ({sql} ORDER BY time_ms DESC, id DESC LIMIT ?)"
            args.append(limit)
        sql += " ORDER BY time_ms, id"
        return [Event.from_dict(json.loads(r[0])) for r in self.conn.execute(sql, args)]

    def record_run(self, run: Run) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO runs (mission, module, started_ms, duration_ms, ok, n_events, error) "
                "VALUES (?,?,?,?,?,?,?)",
                (run.mission, run.module, _ms(run.started), run.duration_ms,
                 int(run.ok), run.n_events, run.error))

    def runs(self, module=None, limit=50):
        sql, args = "SELECT mission, module, started_ms, duration_ms, ok, n_events, error FROM runs", []
        if module is not None:
            sql += " WHERE module = ?"; args.append(module)
        sql += " ORDER BY started_ms DESC, id DESC LIMIT ?"; args.append(limit)
        return [Run(m, mod, _dt(s), d, bool(ok), n, err)
                for m, mod, s, d, ok, n, err in self.conn.execute(sql, args)]

    def close(self) -> None:
        self.conn.close()
