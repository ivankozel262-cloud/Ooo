from pathlib import Path

import httpx
import pytest

from core import cli

SAMPLE = (Path(__file__).parent.parent / "plugins" / "usgs_quakes" / "sample.geojson").read_text()


@pytest.fixture
def usgs(monkeypatch, tmp_path):
    monkeypatch.setenv("SISTEMA_DB", str(tmp_path / "test.db"))
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=SAMPLE))
    monkeypatch.setattr(cli, "make_http", lambda: httpx.Client(transport=transport))


def test_run_planet_then_events(usgs, capsys):
    assert cli.main(["run", "planet"]) == 0
    out = capsys.readouterr().out
    assert "Планета: получено 3, новых 3, сигналов 0, ошибок 0" in out
    assert "M 5.4 - 112 km SSE of Lata" in out

    assert cli.main(["run", "planet"]) == 0
    assert "новых 0" in capsys.readouterr().out

    assert cli.main(["events", "--last", "36500d", "--kind", "earthquake"]) == 0
    out = capsys.readouterr().out
    assert "usgs/earthquake" in out and "всего 3" in out


def test_events_empty(usgs, capsys):
    assert cli.main(["events", "--last", "1h"]) == 0
    assert "событий нет" in capsys.readouterr().out


def test_unknown_mission(usgs, capsys):
    assert cli.main(["run", "mars"]) == 2
    assert "planet" in capsys.readouterr().out


def test_failing_source_gives_nonzero_exit(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SISTEMA_DB", str(tmp_path / "test.db"))
    transport = httpx.MockTransport(lambda req: httpx.Response(503, text="down"))
    monkeypatch.setattr(cli, "make_http", lambda: httpx.Client(transport=transport))
    assert cli.main(["run", "planet"]) == 1
    assert "ошибка — collector:usgs_quakes" in capsys.readouterr().out
