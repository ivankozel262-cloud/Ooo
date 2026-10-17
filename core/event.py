"""Контракт события — единый формат всего, что Система узнаёт.

Поля только добавляются, никогда не удаляются и не меняют смысл.
При добавлении поля растёт SCHEMA_VERSION, а старые события читаются как раньше.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1


def _utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        raise ValueError("время события должно быть с часовым поясом (UTC)")
    return t.astimezone(timezone.utc)


@dataclass
class Event:
    source: str                     # откуда: "usgs", "moex", ...
    time: datetime                  # когда это случилось в мире (UTC)
    entity: str                     # о ком/о чём: место, компания, репозиторий
    kind: str                       # тип: "earthquake", "candle", "signal", ...
    values: dict[str, float] = field(default_factory=dict)   # числа
    text: str = ""
    tags: list[str] = field(default_factory=list)
    geo: dict[str, float] | None = None                      # {"lat", "lon", ...}
    id: str = ""                    # уникален; по нему отсекаются дубли
    schema_version: int = SCHEMA_VERSION
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace: list[str] = field(default_factory=list)           # путь через модули

    def __post_init__(self) -> None:
        for name in ("source", "entity", "kind"):
            if not getattr(self, name):
                raise ValueError(f"у события пустое поле {name}")
        self.time = _utc(self.time)
        for k, v in self.values.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"values[{k!r}] должно быть числом, а не {v!r}")
            self.values[k] = float(v)
        if not self.id:
            key = f"{self.source}|{self.kind}|{self.entity}|{self.time.isoformat()}"
            self.id = f"{self.source}:" + hashlib.sha1(key.encode()).hexdigest()[:16]

    def passed(self, module: str) -> "Event":
        """Отметить, что событие прошло через модуль (это читает рентген)."""
        self.trace.append(module)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "trace": list(self.trace),
            "source": self.source,
            "time": self.time.isoformat(),
            "entity": self.entity,
            "kind": self.kind,
            "values": dict(self.values),
            "text": self.text,
            "tags": list(self.tags),
            "geo": dict(self.geo) if self.geo is not None else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Event":
        # Незнакомые поля из будущих версий пропускаем — так старое ядро не падает.
        known = {f for f in cls.__dataclass_fields__}
        data = {k: v for k, v in d.items() if k in known}
        data["time"] = datetime.fromisoformat(data["time"])
        return cls(**data)
