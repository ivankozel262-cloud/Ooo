"""Контракт хранилища: его проходит любой адаптер (SQLite сейчас, другие потом)."""

from datetime import datetime, timedelta, timezone

import pytest

from core.event import Event
from core.storage import Run
from core.storage_sqlite import SQLiteStorage

T = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(params=["memory", "file"])
def storage(request, tmp_path):
    s = SQLiteStorage(":memory:" if request.param == "memory" else tmp_path / "s.db")
    yield s
    s.close()


def ev(minute, **kw):
    base = dict(source="test", time=T + timedelta(minutes=minute), entity=f"e{minute}", kind="ping")
    base.update(kw)
    return Event(**base)


def test_save_returns_only_new(storage):
    a, b = ev(1), ev(2)
    assert storage.save([a, b]) == [a, b]
    assert storage.save([a, ev(3)])[0].entity == "e3"
    assert len(storage.query()) == 3


def test_roundtrip_keeps_all_fields(storage):
    e = ev(1, values={"mag": 5.1}, text="Сильное", tags=["x"], geo={"lat": 1.5, "lon": -2.0})
    e.passed("collector:test")
    storage.save([e])
    assert storage.query() == [e]


def test_query_period_is_half_open_and_sorted(storage):
    storage.save([ev(5), ev(1), ev(3)])
    got = storage.query(since=T + timedelta(minutes=1), until=T + timedelta(minutes=5))
    assert [e.entity for e in got] == ["e1", "e3"]


def test_query_filters_and_limit(storage):
    storage.save([ev(1), ev(2, source="other"), ev(3, kind="pong"), ev(4)])
    assert [e.entity for e in storage.query(source="test", kind="ping")] == ["e1", "e4"]
    assert [e.entity for e in storage.query(limit=2)] == ["e3", "e4"]


def test_runs_are_recorded_newest_first(storage):
    storage.record_run(Run("m", "collector:a", T, 10, True, 3))
    storage.record_run(Run("m", "collector:a", T + timedelta(minutes=1), 5, False, 0, "boom"))
    storage.record_run(Run("m", "collector:b", T, 1, True, 1))
    runs = storage.runs("collector:a")
    assert [r.ok for r in runs] == [False, True]
    assert runs[0].error == "boom" and runs[0].started == T + timedelta(minutes=1)


def test_reopening_keeps_data_and_does_not_remigrate(tmp_path):
    s = SQLiteStorage(tmp_path / "s.db")
    s.save([ev(1)])
    s.close()
    s = SQLiteStorage(tmp_path / "s.db")
    assert len(s.query()) == 1
    s.close()
