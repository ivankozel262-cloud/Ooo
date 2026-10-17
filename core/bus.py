"""Шина событий: органы общаются через неё, а не напрямую.

Сейчас шина живёт внутри одного процесса (LocalBus). Контракт маленький,
поэтому позже её можно заменить на внешнюю, не трогая органы.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger(__name__)

Handler = Callable[[str, Any], None]

# Темы, которые публикует ядро.
EVENT = "event"      # новое событие сохранено
SIGNAL = "signal"    # детектор нашёл важное
RUN = "run"          # модуль закончил работу (Run)
ALL = "*"            # подписка на всё сразу (так слушает рентген)


class Bus(ABC):
    @abstractmethod
    def subscribe(self, topic: str, handler: Handler) -> None: ...

    @abstractmethod
    def publish(self, topic: str, payload: Any) -> None: ...


class LocalBus(Bus):
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self.errors: list[tuple[str, Exception]] = []

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)

    def publish(self, topic: str, payload: Any) -> None:
        for h in self._handlers[topic] + self._handlers[ALL]:
            try:
                h(topic, payload)
            except Exception as exc:  # сломанный слушатель не должен ронять остальных
                log.exception("слушатель шины упал на теме %s", topic)
                self.errors.append((topic, exc))
