from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

from mta_app.feeds import FEEDS
from mta_app.models import AppConfig, StationConfig, Settings


def _require(d: Dict[str, Any], key: str, where: str) -> Any:
    if key not in d:
        raise ValueError(f"Missing '{key}' in {where}")
    return d[key]


def load_settings(path: str) -> Settings:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Settings file not found: {p.resolve()}")

    raw = json.loads(p.read_text(encoding="utf-8"))

    app_raw = _require(raw, "app", "root")
    stations_raw = _require(raw, "stations", "root")

    app = AppConfig(
        poll_interval_sec=int(_require(app_raw, "poll_interval_sec", "app")),
        print_limit=int(_require(app_raw, "print_limit", "app")),
        run_for_sec=int(_require(app_raw, "run_for_sec", "app")),
        http_timeout_sec=int(_require(app_raw, "http_timeout_sec", "app")),
    )

    if app.poll_interval_sec <= 0:
        raise ValueError("app.poll_interval_sec must be > 0")
    if app.print_limit <= 0:
        raise ValueError("app.print_limit must be > 0")
    if app.run_for_sec < 0:
        raise ValueError("app.run_for_sec must be >= 0")
    if app.http_timeout_sec <= 0:
        raise ValueError("app.http_timeout_sec must be > 0")

    stations: List[StationConfig] = []
    if not isinstance(stations_raw, list) or len(stations_raw) == 0:
        raise ValueError("stations must be a non-empty list")

    for i, s in enumerate(stations_raw):
        where = f"stations[{i}]"
        name = str(_require(s, "name", where))
        feed = str(_require(s, "feed", where))
        stop_id = str(_require(s, "stop_id", where))
        run_for_sec = int(s.get("run_for_sec", 0))

        if feed not in FEEDS:
            raise ValueError(f"{where}.feed='{feed}' not in supported feeds: {sorted(FEEDS.keys())}")
        if not stop_id:
            raise ValueError(f"{where}.stop_id cannot be empty")
        if run_for_sec < 0:
            raise ValueError(f"{where}.run_for_sec must be >= 0")

        stations.append(StationConfig(name=name, feed=feed, stop_id=stop_id, run_for_sec=run_for_sec))

    return Settings(app=app, stations=stations)
