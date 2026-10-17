"""Сборщик землетрясений USGS (Геологическая служба США).

Фиды бесплатные и обновляются каждую минуту:
https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from core.event import Event
from core.plugin import Collector, Context

URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson"
FEED = re.compile(r"(significant|4\.5|2\.5|1\.0|all)_(hour|day|week|month)")
NUMBERS = {  # поле USGS → имя в values
    "mag": "mag", "sig": "sig", "felt": "felt", "cdi": "cdi", "mmi": "mmi",
    "tsunami": "tsunami", "nst": "nst", "gap": "gap", "rms": "rms",
}


class UsgsQuakes(Collector):
    name = "usgs_quakes"
    description = "Землетрясения по всему миру из фидов USGS"
    defaults = {"feed": "all_hour"}
    sample = "sample.geojson"

    def __init__(self, **params):
        super().__init__(**params)
        if not FEED.fullmatch(self.params["feed"]):
            raise ValueError(f"usgs_quakes: неизвестный фид {self.params['feed']!r}; "
                             "пример: all_hour, 2.5_day, significant_week")

    def collect(self, ctx: Context) -> list[Event]:
        resp = ctx.http.get(URL.format(feed=self.params["feed"]), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection" \
                or not isinstance(data.get("features"), list):
            raise ValueError("формат USGS изменился: нет FeatureCollection со списком features")
        return [self._event(f) for f in data["features"]]

    @staticmethod
    def _event(f: dict) -> Event:
        try:
            p = f["properties"]
            lon, lat, depth = f["geometry"]["coordinates"][:3]
            time = datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc)
            qid = f["id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"формат USGS изменился: не разобрать землетрясение "
                             f"{f.get('id') if isinstance(f, dict) else f!r}: {exc!r}") from exc
        values = {name: p[k] for k, name in NUMBERS.items() if isinstance(p.get(k), (int, float))}
        if isinstance(depth, (int, float)):
            values["depth_km"] = depth
        tags = [f"{k}:{p[k]}" for k in ("type", "magType", "net", "status", "alert") if p.get(k)]
        if p.get("tsunami") == 1:
            tags.append("tsunami")
        return Event(
            id=f"usgs:{qid}", source="usgs", time=time, kind="earthquake",
            entity=p.get("place") or qid, text=p.get("title") or "",
            values=values, tags=tags, geo={"lat": lat, "lon": lon},
        )
