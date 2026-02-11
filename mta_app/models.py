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
    name: str
    feed: str
    stop_id: str
    run_for_sec: int  # 0 => inherit from app


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
