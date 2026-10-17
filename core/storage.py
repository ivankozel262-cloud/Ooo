"""Контракт хранилища. Ядро говорит с базой только через него.

Сейчас реализация одна — SQLite (core/storage_sqlite.py). Завтра можно
подключить другую, если она проходит tests/contracts/test_storage_contract.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from core.event import Event


@dataclass
class Run:
    """Один запуск одного модуля: из этого рентген берёт статус, а иммунитет — сбои."""
    mission: str
    module: str
    started: datetime
    duration_ms: int
    ok: bool
    n_events: int = 0
    error: str | None = None


class Storage(ABC):
    @abstractmethod
    def save(self, events: Iterable[Event]) -> list[Event]:
        """Сохранить события; вернуть только новые (дубли по id пропускаются)."""

    @abstractmethod
    def known_ids(self, ids: Iterable[str]) -> set[str]:
        """Какие из этих id уже есть в базе."""

    @abstractmethod
    def query(self, since: datetime | None = None, until: datetime | None = None,
              source: str | None = None, kind: str | None = None,
              limit: int | None = None) -> list[Event]:
        """События за период [since, until) по времени события, от старых к новым."""

    @abstractmethod
    def record_run(self, run: Run) -> None: ...

    @abstractmethod
    def runs(self, module: str | None = None, limit: int = 50) -> list[Run]:
        """Последние запуски, от новых к старым."""

    def close(self) -> None:
        pass
