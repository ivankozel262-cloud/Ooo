"""Контракт плагина: его автоматически проходит КАЖДЫЙ плагин из plugins/.

Новый плагин попадает сюда сам — ничего дописывать не нужно.
"""

import inspect
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from core.bus import LocalBus
from core.event import Event
from core.plugin import KINDS, Collector, Context, Plugin
from core.registry import Registry
from core.storage_sqlite import SQLiteStorage

PLUGINS = Registry.discover().all()
COLLECTORS = [p for p in PLUGINS if issubclass(p, Collector)]


def ids(classes):
    return [f"{c.kind}:{c.name}" for c in classes]


def test_there_are_plugins():
    assert PLUGINS, "реестр не нашёл ни одного плагина"


@pytest.mark.parametrize("cls", PLUGINS, ids=ids(PLUGINS))
def test_plugin_shape(cls):
    assert issubclass(cls, Plugin)
    assert cls.name and cls.name.isidentifier(), "name — латиница, цифры и _"
    assert cls.kind in KINDS
    assert cls.description, "у плагина должно быть описание — его покажет рентген"
    cls()  # создаётся с параметрами по умолчанию


@pytest.mark.parametrize("cls", PLUGINS, ids=ids(PLUGINS))
def test_plugin_has_own_tests(cls):
    folder = Path(inspect.getfile(cls)).parent
    assert list(folder.glob("test_*.py")), f"у плагина {cls.name} нет тестов рядом с кодом"


@pytest.mark.parametrize("cls", COLLECTORS, ids=ids(COLLECTORS))
def test_collector_turns_its_sample_into_valid_events(cls):
    assert cls.sample, "у сборщика должен быть файл-образец ответа источника"
    sample = (Path(inspect.getfile(cls)).parent / cls.sample).read_bytes()
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=sample)))
    ctx = Context(mission="contract", now=datetime.now(timezone.utc),
                  storage=SQLiteStorage(":memory:"), bus=LocalBus(), http=http)
    events = cls().collect(ctx)
    assert events, "на образце сборщик должен найти хотя бы одно событие"
    assert all(isinstance(e, Event) for e in events)
    assert len({e.id for e in events}) == len(events), "id событий должны быть уникальны"
    for e in events:
        assert Event.from_dict(e.to_dict()) == e
