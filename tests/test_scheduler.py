from datetime import datetime, timedelta, timezone

from core.scheduler import Scheduler

T0 = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


def test_runs_immediately_then_on_schedule():
    clock, ran = Clock(), []
    s = Scheduler({"fast": timedelta(minutes=1), "slow": timedelta(minutes=5)}, ran.append, clock)
    assert s.tick() == 60
    assert ran == ["fast", "slow"]
    clock.now = T0 + timedelta(seconds=30)
    s.tick()
    assert ran == ["fast", "slow"]
    clock.now = T0 + timedelta(minutes=1)
    s.tick()
    assert ran == ["fast", "slow", "fast"]


def test_after_sleep_runs_once_not_a_burst():
    clock, ran = Clock(), []
    s = Scheduler({"job": timedelta(minutes=1)}, ran.append, clock)
    s.tick()
    clock.now = T0 + timedelta(hours=3)
    s.tick()
    s.tick()
    assert ran == ["job", "job"]
    assert s.next_at["job"] == clock.now + timedelta(minutes=1)


def test_failing_job_does_not_stop_others():
    clock, ran = Clock(), []

    def run(name):
        if name == "bad":
            raise RuntimeError("boom")
        ran.append(name)

    Scheduler({"bad": timedelta(minutes=1), "good": timedelta(minutes=1)}, run, clock).tick()
    assert ran == ["good"]
