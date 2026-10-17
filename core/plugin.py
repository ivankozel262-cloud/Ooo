"""Интерфейсы плагинов четырёх видов: сборщик → обогатитель → детектор → выход.

Плагин — это класс в папке plugins/ с именем (name) и видом (kind).
Параметры приходят из миссии; неизвестный параметр — ошибка, чтобы опечатка
в YAML не проходила молча.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

import httpx

from core.bus import Bus
from core.event import Event
from core.storage import Storage

KINDS = ("collector", "enricher", "detector", "output")


@dataclass
class Context:
    """Что ядро даёт плагину на время запуска. Сеть — только через http."""
    mission: str
    now: datetime
    storage: Storage
    bus: Bus
    http: httpx.Client


class Plugin:
    name: ClassVar[str] = ""
    kind: ClassVar[str] = ""
    description: ClassVar[str] = ""
    defaults: ClassVar[dict[str, Any]] = {}

    def __init__(self, **params: Any) -> None:
        unknown = set(params) - set(self.defaults)
        if unknown:
            raise ValueError(f"{self.module}: неизвестные параметры {sorted(unknown)}; "
                             f"можно: {sorted(self.defaults)}")
        self.params = {**self.defaults, **params}

    @property
    def module(self) -> str:
        return f"{self.kind}:{self.name}"


class Collector(Plugin):
    """Тянет данные из внешнего мира и превращает их в события."""
    kind = "collector"
    # Файл-образец ответа источника рядом с плагином: на нём проверяют
    # тесты-контракты (без сети) и на нём же иммунитет будет чинить плагин.
    sample: ClassVar[str | None] = None

    def collect(self, ctx: Context) -> list[Event]:
        raise NotImplementedError


class Enricher(Plugin):
    """Дополняет события: теги, числа, разбор текста."""
    kind = "enricher"

    def enrich(self, events: list[Event], ctx: Context) -> list[Event]:
        raise NotImplementedError


class Detector(Plugin):
    """Ищет важное и возвращает сигналы — тоже события, kind="signal"."""
    kind = "detector"

    def detect(self, events: list[Event], ctx: Context) -> list[Event]:
        raise NotImplementedError


class Output(Plugin):
    """Сообщает наружу: «Входящие», reports/, Telegram…"""
    kind = "output"

    def emit(self, events: list[Event], ctx: Context) -> None:
        raise NotImplementedError
