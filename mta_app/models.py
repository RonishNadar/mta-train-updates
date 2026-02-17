# mta_app/models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AppConfig:
    poll_interval_sec: int
    print_limit: int
    run_for_sec: int
    http_timeout_sec: int


@dataclass(frozen=True)
class StationConfig:
    stop_name: str
    gtfs_stop_id: str      # base id, e.g. "N03"
    direction: str         # "N" or "S"
    direction_label: str   # e.g. "Manhattan"
    feed: str              # e.g. "NQRW"
    run_for_sec: int       # 0 => inherit from app

    @property
    def rt_stop_id(self) -> str:
        # realtime stop_id used in GTFS-RT feed, e.g. "N03N"
        return f"{self.gtfs_stop_id}{self.direction}"


@dataclass(frozen=True)
class Settings:
    app: AppConfig
    stations: List[StationConfig]


@dataclass(frozen=True)
class Arrival:
    route_id: str
    trip_id: str
    eta_epoch: int
    eta_min: int
