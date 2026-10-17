"""Команда `sistema` — пульт управления Системой."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

import httpx

from core.bus import LocalBus
from core.config import db_path, load_dotenv
from core.event import Event
from core.mission import MissionError, load_missions, parse_every
from core.registry import Registry
from core.runner import RunResult, run_mission
from core.scheduler import Scheduler
from core.storage_sqlite import SQLiteStorage


def make_http() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": "sistema/0.1"}, follow_redirects=True)


def fmt_event(e: Event) -> str:
    when = e.time.astimezone().strftime("%Y-%m-%d %H:%M")
    nums = " ".join(f"{k}={v:g}" for k, v in list(e.values.items())[:3])
    return f"{when}  {e.source}/{e.kind:<10}  {e.text or e.entity}  {nums}".rstrip()


def summary(m_title: str, res: RunResult) -> str:
    line = (f"{m_title}: получено {res.collected}, новых {len(res.new)}, "
            f"сигналов {len(res.signals)}, ошибок {len(res.errors)}")
    return "\n".join([line] + [f"  ошибка — {e}" for e in res.errors])


def cmd_run(args) -> int:
    missions = load_missions()
    if args.mission not in missions:
        print(f"Нет миссии {args.mission!r}. Есть: {', '.join(sorted(missions)) or 'пока ни одной'}")
        return 2
    m = missions[args.mission]
    storage = SQLiteStorage(db_path())
    with make_http() as http:
        res = run_mission(m, Registry.discover(), storage, LocalBus(), http)
    storage.close()
    print(summary(m.title or m.name, res))
    for e in res.new[-10:]:
        print("  + " + fmt_event(e))
    if len(res.new) > 10:
        print(f"  … и ещё {len(res.new) - 10}")
    return 1 if res.errors else 0


def cmd_events(args) -> int:
    since = datetime.now(timezone.utc) - parse_every(args.last)
    storage = SQLiteStorage(db_path())
    events = storage.query(since=since, source=args.source, kind=args.kind, limit=args.limit)
    storage.close()
    if not events:
        print(f"За последние {args.last} событий нет.")
        return 0
    for e in events:
        print(fmt_event(e))
    print(f"— всего {len(events)} за последние {args.last}")
    return 0


def cmd_serve(args) -> int:
    missions = {n: m for n, m in load_missions().items() if m.every}
    if not missions:
        print("Нет миссий с расписанием.")
        return 2
    registry, storage, bus = Registry.discover(), SQLiteStorage(db_path()), LocalBus()
    http = make_http()

    def run(name: str) -> None:
        m = missions[name]
        res = run_mission(m, registry, storage, bus, http)
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] {summary(m.title or m.name, res)}", flush=True)

    print("Система работает. Миссии: " +
          ", ".join(f"{m.title or n} (каждые {m.every})" for n, m in missions.items()) +
          ". Остановить — Ctrl+C.", flush=True)
    try:
        Scheduler({n: m.every for n, m in missions.items()}, run).run_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        http.close()
        storage.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sistema", description="Система — живой механизм наблюдения.")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="один раз прогнать миссию")
    r.add_argument("mission", help="имя миссии, например planet")
    r.set_defaults(fn=cmd_run)

    e = sub.add_parser("events", help="показать события за период")
    e.add_argument("--last", default="1h", help="период: 30m, 1h, 2d (по умолчанию 1h)")
    e.add_argument("--source", help="только этот источник, например usgs")
    e.add_argument("--kind", help="только этот тип, например earthquake")
    e.add_argument("--limit", type=int, default=200, help="не больше стольких последних")
    e.set_defaults(fn=cmd_events)

    s = sub.add_parser("serve", help="работать постоянно: миссии по расписанию")
    s.set_defaults(fn=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except MissionError as exc:
        print(f"Ошибка в миссии: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
