from datetime import timedelta

import pytest

from core.mission import MissionError, load_mission, load_missions, parse_every


def write(tmp_path, text, name="m.yaml"):
    p = tmp_path / name
    p.write_text(text)
    return p


@pytest.mark.parametrize("text,delta", [("30s", timedelta(seconds=30)), ("1m", timedelta(minutes=1)),
                                        ("2h", timedelta(hours=2)), ("1d", timedelta(days=1))])
def test_parse_every(text, delta):
    assert parse_every(text) == delta


@pytest.mark.parametrize("bad", ["", "0m", "5 minutes", "1w", "m"])
def test_parse_every_rejects(bad):
    with pytest.raises(MissionError):
        parse_every(bad)


def test_load_full_mission(tmp_path):
    m = load_mission(write(tmp_path, """
name: demo
title: Демо
schedule: {every: 5m}
collectors:
  - plugin: src
    params: {feed: x}
detectors: [big]
"""))
    assert m.name == "demo" and m.every == timedelta(minutes=5)
    assert m.steps["collector"][0].plugin == "src" and m.steps["collector"][0].params == {"feed": "x"}
    assert m.steps["detector"][0].plugin == "big" and m.steps["output"] == []


@pytest.mark.parametrize("text", [
    "title: no name\ncollectors: [a]",
    "name: x",
    "name: x\ncollectors: [a]\ncolectors: [b]",
    "name: x\ncollectors: [{plugin: a, parms: {}}]",
])
def test_bad_missions_rejected(tmp_path, text):
    with pytest.raises(MissionError):
        load_mission(write(tmp_path, text))


def test_load_missions_rejects_duplicates(tmp_path):
    write(tmp_path, "name: a\ncollectors: [x]", "1.yaml")
    write(tmp_path, "name: a\ncollectors: [x]", "2.yaml")
    with pytest.raises(MissionError):
        load_missions(tmp_path)
