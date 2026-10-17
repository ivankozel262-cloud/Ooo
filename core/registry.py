"""Реестр плагинов: сам находит их в папке plugins/ — регистрировать вручную не нужно."""

from __future__ import annotations

import importlib
import inspect
import pkgutil

from core.plugin import KINDS, Plugin


class Registry:
    def __init__(self) -> None:
        self._plugins: dict[tuple[str, str], type[Plugin]] = {}

    def add(self, cls: type[Plugin]) -> None:
        if not cls.name:
            raise ValueError(f"у плагина {cls.__qualname__} нет name")
        if cls.kind not in KINDS:
            raise ValueError(f"плагин {cls.name}: неизвестный вид {cls.kind!r}")
        key = (cls.kind, cls.name)
        if key in self._plugins and self._plugins[key] is not cls:
            raise ValueError(f"два плагина с одним именем: {cls.kind}:{cls.name}")
        self._plugins[key] = cls

    def get(self, kind: str, name: str) -> type[Plugin]:
        try:
            return self._plugins[(kind, name)]
        except KeyError:
            known = sorted(n for k, n in self._plugins if k == kind)
            raise KeyError(f"нет плагина {kind}:{name}; есть: {known}") from None

    def all(self) -> list[type[Plugin]]:
        return [self._plugins[k] for k in sorted(self._plugins)]

    @classmethod
    def discover(cls, package: str = "plugins") -> "Registry":
        reg = cls()
        pkg = importlib.import_module(package)
        modules = [pkg] + [
            importlib.import_module(info.name)
            for info in pkgutil.walk_packages(pkg.__path__, prefix=f"{package}.")
            if not info.name.rsplit(".", 1)[-1].startswith(("test", "conftest"))
        ]
        for mod in modules:
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                # Только классы, объявленные в этом модуле, — не импортированные базовые.
                if issubclass(obj, Plugin) and obj.__module__ == mod.__name__ and obj.name:
                    reg.add(obj)
        return reg
