"""Один прогон миссии: сборщики → обогатители → хранилище → детекторы → выходы.

Сбой одного модуля не роняет прогон: ошибка записывается в журнал запусков
и уходит в шину, остальные модули работают дальше.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import httpx

from core.bus import EVENT, RUN, SIGNAL, Bus
from core.event import Event
from core.mission import Mission
from core.plugin import Context, Plugin
from core.registry import Registry
from core.storage import Run, Storage

STORAGE = "core:storage"


@dataclass
class RunResult:
    mission: str
    collected: int = 0
    new: list[Event] = field(default_factory=list)
    signals: list[Event] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_mission(mission: Mission, registry: Registry, storage: Storage, bus: Bus,
                http: httpx.Client, now: datetime | None = None) -> RunResult:
    now = now or datetime.now(timezone.utc)
    ctx = Context(mission=mission.name, now=now, storage=storage, bus=bus, http=http)
    # Сначала создаём все плагины: ошибка в миссии видна до любого сбора.
    plugins: dict[str, list[Plugin]] = {
        kind: [registry.get(kind, s.plugin)(**s.params) for s in steps]
        for kind, steps in mission.steps.items()
    }
    res = RunResult(mission.name)

    def step(p: Plugin, fn: Callable[[], list[Event] | None]) -> list[Event] | None:
        t0, started = time.monotonic(), datetime.now(timezone.utc)
        try:
            out = fn()
            err = None
        except Exception as exc:
            out, err = None, f"{type(exc).__name__}: {exc}"
            res.errors.append(f"{p.module}: {err}")
        run = Run(mission.name, p.module, started, int((time.monotonic() - t0) * 1000),
                  err is None, len(out or []), err)
        storage.record_run(run)
        bus.publish(RUN, run)
        return out

    events: list[Event] = []
    for c in plugins["collector"]:
        got = step(c, lambda c=c: c.collect(ctx)) or []
        events += [e.passed(c.module) for e in got]
    res.collected = len(events)

    # Уже известное дальше не идёт: не тратим силы (и будущие вызовы AI) на дубли.
    known = storage.known_ids([e.id for e in events])
    events = [e for e in events if e.id not in known]

    for en in plugins["enricher"]:
        out = step(en, lambda en=en: en.enrich(events, ctx))
        if out is not None:
            events = [e.passed(en.module) for e in out]

    res.new = storage.save([e.passed(STORAGE) for e in events])
    for e in res.new:
        bus.publish(EVENT, e)

    for d in plugins["detector"]:
        out = step(d, lambda d=d: d.detect(res.new, ctx)) or []
        found = storage.save([s.passed(d.module).passed(STORAGE) for s in out])
        res.signals += found
        for s in found:
            bus.publish(SIGNAL, s)

    for o in plugins["output"]:
        step(o, lambda o=o: o.emit(res.new + res.signals, ctx))
    return res
