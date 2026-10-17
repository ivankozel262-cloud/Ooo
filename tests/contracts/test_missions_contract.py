"""Контракт миссий: каждая миссия из missions/ читается, а её плагины существуют."""

import pytest

from core.mission import load_missions
from core.registry import Registry

MISSIONS = load_missions()
REGISTRY = Registry.discover()


@pytest.mark.parametrize("name", sorted(MISSIONS))
def test_mission_plugins_exist_and_accept_params(name):
    m = MISSIONS[name]
    assert m.title, "у миссии должно быть название для рентгена"
    for kind, steps in m.steps.items():
        for s in steps:
            REGISTRY.get(kind, s.plugin)(**s.params)


def test_planet_mission_is_there():
    assert "planet" in MISSIONS
