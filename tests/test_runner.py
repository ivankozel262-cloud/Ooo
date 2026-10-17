from datetime import datetime, timezone

import httpx
import pytest

from core.bus import EVENT, RUN, SIGNAL, LocalBus
from core.event import Event
from core.mission import Mission, Step
from core.plugin import Collector, Detector, Enricher, Output
from core.registry import Registry
from core.runner import run_mission
from core.storage_sqlite import SQLiteStorage

T = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
emitted = []


class Numbers(Collector):
    name = "numbers"
    defaults = {"n": 3}

    def collect(self, ctx):
        return [Event(source="num", time=T, entity=f"n{i}", kind="num", values={"v": i})
                for i in range(self.params["n"])]


class Broken(Collector):
    name = "broken"

    def collect(self, ctx):
        raise ValueError("источник сменил формат")


class Tagger(Enricher):
    name = "tagger"

    def enrich(self, events, ctx):
        for e in events:
            e.tags.append("seen")
        return events


class Big(Detector):
    name = "big"

    def detect(self, events, ctx):
        return [Event(source="big", time=e.time, entity=e.entity, kind="signal", text="большое")
                for e in events if e.values["v"] >= 2]


class Collect(Output):
    name = "collect"

    def emit(self, events, ctx):
        emitted.extend(events)


@pytest.fixture
def env():
    reg = Registry()
    for p in (Numbers, Broken, Tagger, Big, Collect):
        reg.add(p)
    storage, bus, heard = SQLiteStorage(":memory:"), LocalBus(), []
    bus.subscribe("*", lambda t, p: heard.append(t))
    emitted.clear()
    yield reg, storage, bus, heard
    storage.close()


def mission(*collectors):
    m = Mission("demo")
    m.steps["collector"] = [Step(c) for c in collectors]
    m.steps["enricher"] = [Step("tagger")]
    m.steps["detector"] = [Step("big")]
    m.steps["output"] = [Step("collect")]
    return m


def test_full_pipeline(env):
    reg, storage, bus, heard = env
    res = run_mission(mission("numbers"), reg, storage, bus, httpx.Client(), now=T)
    assert res.collected == 3 and len(res.new) == 3 and not res.errors
    assert all("seen" in e.tags for e in res.new)
    assert res.new[0].trace == ["collector:numbers", "enricher:tagger", "core:storage"]
    assert [s.entity for s in res.signals] == ["n2"]
    assert res.signals[0].trace == ["detector:big", "core:storage"]
    assert len(emitted) == 4
    assert heard.count(EVENT) == 3 and heard.count(SIGNAL) == 1 and heard.count(RUN) == 4
    assert len(storage.query()) == 4


def test_second_run_adds_no_duplicates(env):
    reg, storage, bus, _ = env
    run_mission(mission("numbers"), reg, storage, bus, httpx.Client(), now=T)
    res = run_mission(mission("numbers"), reg, storage, bus, httpx.Client(), now=T)
    assert res.collected == 3 and res.new == [] and res.signals == []
    assert len(storage.query()) == 4


def test_broken_collector_is_recorded_and_others_continue(env):
    reg, storage, bus, _ = env
    res = run_mission(mission("broken", "numbers"), reg, storage, bus, httpx.Client(), now=T)
    assert len(res.new) == 3
    assert res.errors == ["collector:broken: ValueError: источник сменил формат"]
    last = storage.runs("collector:broken")[0]
    assert not last.ok and "сменил формат" in last.error


def test_mission_with_unknown_plugin_fails_before_collecting(env):
    reg, storage, bus, _ = env
    with pytest.raises(KeyError):
        run_mission(mission("numbers", "ghost"), reg, storage, bus, httpx.Client(), now=T)
    assert storage.runs() == []
