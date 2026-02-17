# mta_app/config.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    temp_unit = str(app_raw.get("temp_unit", "C")).strip().upper()
    if temp_unit not in ("C", "F"):
        temp_unit = "C"

    leave_buffer_min = int(app_raw.get("leave_buffer_min", 10))
    if leave_buffer_min < 0:
        leave_buffer_min = 0
    if leave_buffer_min > 60:
        leave_buffer_min = 60

    fav_idx_raw = app_raw.get("favorite_station_index", None)
    favorite_station_index: Optional[int] = None
    if fav_idx_raw is not None:
        try:
            favorite_station_index = int(fav_idx_raw)
        except Exception:
            favorite_station_index = None

    app = AppConfig(
        poll_interval_sec=int(_require(app_raw, "poll_interval_sec", "app")),
        print_limit=int(_require(app_raw, "print_limit", "app")),
        run_for_sec=int(_require(app_raw, "run_for_sec", "app")),
        http_timeout_sec=int(_require(app_raw, "http_timeout_sec", "app")),
        temp_unit=temp_unit,
        leave_buffer_min=leave_buffer_min,
        favorite_station_index=favorite_station_index,
    )

    if app.poll_interval_sec <= 0:
        raise ValueError("app.poll_interval_sec must be > 0")
    if app.print_limit <= 0:
        raise ValueError("app.print_limit must be > 0")
    if app.run_for_sec < 0:
        raise ValueError("app.run_for_sec must be >= 0")
    if app.http_timeout_sec <= 0:
        raise ValueError("app.http_timeout_sec must be > 0")

    if not isinstance(stations_raw, list) or len(stations_raw) == 0:
        raise ValueError("stations must be a non-empty list")

    stations: List[StationConfig] = []
    for i, s in enumerate(stations_raw):
        where = f"stations[{i}]"

        stop_name = str(_require(s, "stop_name", where))
        gtfs_stop_id = str(_require(s, "gtfs_stop_id", where)).strip()
        direction = str(_require(s, "direction", where)).strip().upper()
        direction_label = str(_require(s, "direction_label", where)).strip()
        feed = str(_require(s, "feed", where)).strip()
        run_for_sec = int(s.get("run_for_sec", 0))

        if feed not in FEEDS:
            raise ValueError(
                f"{where}.feed='{feed}' not in supported feeds: {sorted(FEEDS.keys())}"
            )
        if not gtfs_stop_id:
            raise ValueError(f"{where}.gtfs_stop_id cannot be empty")
        if direction not in ("N", "S"):
            raise ValueError(f"{where}.direction must be 'N' or 'S'")
        if run_for_sec < 0:
            raise ValueError(f"{where}.run_for_sec must be >= 0")

        stations.append(
            StationConfig(
                stop_name=stop_name,
                gtfs_stop_id=gtfs_stop_id,
                direction=direction,
                direction_label=direction_label,
                feed=feed,
                run_for_sec=run_for_sec,
            )
        )

    # Validate favorite index if present
    if app.favorite_station_index is not None:
        if not (0 <= app.favorite_station_index < len(stations)):
            app.favorite_station_index = None

    return Settings(app=app, stations=stations)
