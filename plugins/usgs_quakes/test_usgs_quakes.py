import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from core.bus import LocalBus
from core.plugin import Context
from core.storage_sqlite import SQLiteStorage
from plugins.usgs_quakes import UsgsQuakes

SAMPLE = (Path(__file__).parent / "sample.geojson").read_text()


def ctx_with(handler):
    return Context(mission="t", now=datetime.now(timezone.utc), storage=SQLiteStorage(":memory:"),
                   bus=LocalBus(), http=httpx.Client(transport=httpx.MockTransport(handler)))


def answer(body, status=200):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(status, text=body)
    return handler, seen


def test_parses_sample():
    handler, seen = answer(SAMPLE)
    events = UsgsQuakes().collect(ctx_with(handler))
    assert seen == ["https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"]
    assert len(events) == 3
    strong = events[1]
    assert strong.id == "usgs:us7000r1ab" and strong.kind == "earthquake" and strong.source == "usgs"
    assert strong.entity == "112 km SSE of Lata, Solomon Islands"
    assert strong.values["mag"] == 5.4 and strong.values["depth_km"] == 35 and strong.values["felt"] == 3
    assert strong.geo == {"lat": -11.7, "lon": 166.2}
    assert strong.time == datetime.fromtimestamp(1792229880, tz=timezone.utc)
    assert "alert:green" in strong.tags and "tsunami" in strong.tags


def test_missing_numbers_and_place_are_tolerated():
    handler, _ = answer(SAMPLE)
    blast = UsgsQuakes().collect(ctx_with(handler))[2]
    assert "mag" not in blast.values and blast.entity == "ak0261xyz"
    assert "type:quarry blast" in blast.tags


def test_feed_param():
    handler, seen = answer(SAMPLE)
    UsgsQuakes(feed="2.5_day").collect(ctx_with(handler))
    assert seen[0].endswith("/2.5_day.geojson")
    with pytest.raises(ValueError):
        UsgsQuakes(feed="everything")


def test_changed_format_gives_clear_error():
    handler, _ = answer(json.dumps({"quakes": []}))
    with pytest.raises(ValueError, match="формат USGS изменился"):
        UsgsQuakes().collect(ctx_with(handler))

    broken = json.loads(SAMPLE)
    del broken["features"][0]["properties"]["time"]
    handler, _ = answer(json.dumps(broken))
    with pytest.raises(ValueError, match="nc75012345"):
        UsgsQuakes().collect(ctx_with(handler))


def test_http_error_raises():
    handler, _ = answer("oops", status=503)
    with pytest.raises(httpx.HTTPStatusError):
        UsgsQuakes().collect(ctx_with(handler))
