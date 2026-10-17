"""Настройки: из переменных окружения и файла .env в корне (он не попадает в git)."""

from __future__ import annotations

import os
from pathlib import Path

from core import ROOT


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Прочитать KEY=VALUE из .env; уже заданные переменные не перезаписываются."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def db_path() -> Path:
    return Path(os.environ.get("SISTEMA_DB", ROOT / "data" / "sistema.db"))
