"""Планировщик: запускает задачи (миссии, позже бэкап и самоанализ) по расписанию."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Scheduler:
    def __init__(self, jobs: dict[str, timedelta], run: Callable[[str], None],
                 clock: Callable[[], datetime] = utcnow) -> None:
        self.jobs, self.run, self.clock = dict(jobs), run, clock
        start = clock()
        self.next_at = {name: start for name in self.jobs}   # первый запуск — сразу

    def due(self, now: datetime) -> list[str]:
        """Какие задачи пора запускать; сразу назначает им следующее время."""
        ready = [n for n in self.jobs if self.next_at[n] <= now]
        for n in ready:
            nxt = self.next_at[n] + self.jobs[n]
            # Если компьютер спал и пропущено много запусков — не догоняем пачкой.
            self.next_at[n] = nxt if nxt > now else now + self.jobs[n]
        return ready

    def tick(self) -> float:
        """Запустить всё, что пора; вернуть, сколько секунд можно спать."""
        for name in self.due(self.clock()):
            try:
                self.run(name)
            except Exception:
                log.exception("задача %s упала", name)
        if not self.next_at:
            return 60.0
        return max(0.0, (min(self.next_at.values()) - self.clock()).total_seconds())

    def run_forever(self, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        while not stop.is_set():
            stop.wait(self.tick())
