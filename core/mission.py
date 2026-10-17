"""Миссия — файл missions/<имя>.yaml: какие плагины запускать, с какими
параметрами и как часто. Новая область — новая миссия, а не новый код ядра.

    name: planet
    title: Планета
    schedule: {every: 1m}
    collectors:
      - plugin: usgs_quakes
        params: {feed: all_hour}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml

from core import ROOT
from core.plugin import KINDS

MISSIONS = ROOT / "missions"
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


class MissionError(ValueError):
    pass


@dataclass
class Step:
    plugin: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Mission:
    name: str
    title: str = ""
    description: str = ""
    every: timedelta | None = None          # None — только ручной запуск
    steps: dict[str, list[Step]] = field(default_factory=lambda: {k: [] for k in KINDS})
    path: Path | None = None


def parse_every(text: str) -> timedelta:
    """'30s', '1m', '2h', '1d' → timedelta."""
    m = re.fullmatch(r"\s*(\d+)\s*([smhd])\s*", str(text))
    if not m or int(m.group(1)) == 0:
        raise MissionError(f"не понимаю расписание {text!r}; пример: 30s, 1m, 2h, 1d")
    return timedelta(**{_UNITS[m.group(2)]: int(m.group(1))})


def _step(raw: Any, where: str) -> Step:
    if isinstance(raw, str):
        return Step(raw)
    if isinstance(raw, dict) and isinstance(raw.get("plugin"), str):
        extra = set(raw) - {"plugin", "params"}
        if extra:
            raise MissionError(f"{where}: лишние ключи {sorted(extra)}")
        return Step(raw["plugin"], dict(raw.get("params") or {}))
    raise MissionError(f"{where}: ожидаю имя плагина или {{plugin: …, params: …}}")


def load_mission(path: Path) -> Mission:
    data = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(data, dict) or not data.get("name"):
        raise MissionError(f"{path}: у миссии нет name")
    allowed = {"name", "title", "description", "schedule", *(k + "s" for k in KINDS)}
    extra = set(data) - allowed
    if extra:
        raise MissionError(f"{path}: неизвестные ключи {sorted(extra)}")
    every = (data.get("schedule") or {}).get("every")
    m = Mission(name=str(data["name"]), title=data.get("title", ""),
                description=data.get("description", ""),
                every=parse_every(every) if every else None, path=Path(path))
    for kind in KINDS:
        m.steps[kind] = [_step(s, f"{path}: {kind}s[{i}]")
                         for i, s in enumerate(data.get(kind + "s") or [])]
    if not m.steps["collector"]:
        raise MissionError(f"{path}: у миссии нет ни одного сборщика")
    return m


def load_missions(folder: Path = MISSIONS) -> dict[str, Mission]:
    missions: dict[str, Mission] = {}
    for path in sorted(Path(folder).glob("*.yaml")):
        m = load_mission(path)
        if m.name in missions:
            raise MissionError(f"две миссии с именем {m.name}")
        missions[m.name] = m
    return missions
