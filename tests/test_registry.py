import sys
import textwrap

import pytest

from core.plugin import Collector, Detector
from core.registry import Registry


@pytest.fixture
def fake_package(tmp_path, monkeypatch):
    pkg = tmp_path / "fakeplugins"
    (pkg / "alpha").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "alpha" / "__init__.py").write_text(textwrap.dedent("""
        from core.plugin import Collector, Detector
        class Alpha(Collector):
            name = "alpha"
        class Watch(Detector):
            name = "watch"
    """))
    (pkg / "alpha" / "test_alpha.py").write_text("raise RuntimeError('тесты не импортируются')")
    monkeypatch.syspath_prepend(str(tmp_path))
    yield "fakeplugins"
    for m in [m for m in sys.modules if m.startswith("fakeplugins")]:
        del sys.modules[m]


def test_discovers_plugins_and_skips_tests(fake_package):
    reg = Registry.discover(fake_package)
    assert reg.get("collector", "alpha").name == "alpha"
    assert reg.get("detector", "watch").kind == "detector"
    assert len(reg.all()) == 2


def test_unknown_plugin_error_lists_known(fake_package):
    reg = Registry.discover(fake_package)
    with pytest.raises(KeyError, match="alpha"):
        reg.get("collector", "nope")


def test_duplicate_names_rejected():
    class A(Collector):
        name = "same"

    class B(Collector):
        name = "same"

    reg = Registry()
    reg.add(A)
    with pytest.raises(ValueError):
        reg.add(B)


def test_unknown_params_rejected():
    class P(Detector):
        name = "p"
        defaults = {"min": 1}

    assert P(min=5).params == {"min": 5}
    with pytest.raises(ValueError, match="mni"):
        P(mni=5)
