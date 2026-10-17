"""Контракт события: его обязан соблюдать любой модуль и любое будущее ядро."""

from datetime import datetime, timedelta, timezone

import pytest

from core.event import SCHEMA_VERSION, Event

T = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def make(**kw):
    base = dict(source="test", time=T, entity="X", kind="ping")
    base.update(kw)
    return Event(**base)


def test_has_all_contract_fields():
    d = make().to_dict()
    for f in ("id", "schema_version", "trace_id", "source", "time", "entity",
              "kind", "values", "text", "tags", "geo"):
        assert f in d
    assert d["schema_version"] == SCHEMA_VERSION


def test_roundtrip_keeps_everything():
    e = make(values={"mag": 4.5}, text="hi", tags=["a"], geo={"lat": 1.0, "lon": 2.0})
    e.passed("collector:test")
    back = Event.from_dict(e.to_dict())
    assert back == e


def test_time_is_normalised_to_utc():
    msk = timezone(timedelta(hours=3))
    e = make(time=datetime(2026, 10, 17, 15, 0, tzinfo=msk))
    assert e.time == T and e.time.tzinfo == timezone.utc


def test_naive_time_rejected():
    with pytest.raises(ValueError):
        make(time=datetime(2026, 10, 17))


@pytest.mark.parametrize("field", ["source", "entity", "kind"])
def test_required_fields_not_empty(field):
    with pytest.raises(ValueError):
        make(**{field: ""})


def test_values_must_be_numbers():
    with pytest.raises(ValueError):
        make(values={"mag": "big"})
    assert make(values={"n": 3}).values == {"n": 3.0}


def test_same_fact_same_id_without_explicit_id():
    assert make().id == make().id
    assert make().id != make(entity="Y").id


def test_unknown_future_fields_are_ignored():
    d = make().to_dict()
    d["field_from_the_future"] = 42
    assert Event.from_dict(d).entity == "X"


def test_each_event_gets_own_trace_id():
    assert make().trace_id != make().trace_id
