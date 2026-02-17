# mta_app/weather.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import requests


@dataclass
class WeatherSnapshot:
    condition_text: str          # e.g. "Sunny", "Cloudy"
    condition_kind: str          # one of: sunny/cloudy/rain/snow/fog/storm
    pop_pct: Optional[int]       # 0..100
    temp_c: Optional[float]
    feels_like_c: Optional[float]
    updated_at: float            # unix seconds


# Open-Meteo weather codes:
# https://open-meteo.com/en/docs
def _map_weathercode(code: Optional[int]) -> Tuple[str, str]:
    if code is None:
        return ("-", "cloudy")

    # Clear
    if code == 0:
        return ("Clear", "sunny")
    if code in (1, 2):
        return ("Partly cloudy", "cloudy")
    if code == 3:
        return ("Overcast", "cloudy")

    # Fog
    if code in (45, 48):
        return ("Fog", "fog")

    # Drizzle / rain
    if code in (51, 53, 55):
        return ("Drizzle", "rain")
    if code in (56, 57):
        return ("Freezing drizzle", "snow")

    if code in (61, 63, 65):
        return ("Rain", "rain")
    if code in (66, 67):
        return ("Freezing rain", "snow")

    # Snow
    if code in (71, 73, 75):
        return ("Snow", "snow")
    if code == 77:
        return ("Snow grains", "snow")

    # Showers
    if code in (80, 81, 82):
        return ("Showers", "rain")

    # Thunderstorm
    if code in (95,):
        return ("Thunderstorm", "storm")
    if code in (96, 99):
        return ("Thunderstorm", "storm")

    return ("Weather", "cloudy")


def _nearest_hour_index(times: list[str], target_iso: str) -> int:
    """
    times: list of ISO strings like "2026-02-17T02:00"
    target_iso: same format
    Returns best index (exact if found, else closest by string compare).
    """
    # exact match first
    try:
        return times.index(target_iso)
    except ValueError:
        pass

    # fallback: closest by lexical distance (ISO format sorts)
    # find first time >= target
    for i, t in enumerate(times):
        if t >= target_iso:
            return i
    return max(0, len(times) - 1)


def fetch_weather_open_meteo(
    lat: float,
    lon: float,
    *,
    timeout_s: float = 6.0,
) -> WeatherSnapshot:
    """
    Fetches current condition + POP + temp + feels-like from Open-Meteo.
    No API key needed.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        # hourly: precipitation probability + apparent temp (feels-like)
        "hourly": "precipitation_probability,apparent_temperature",
        # optional: get temps in C; you can convert to F in UI
        "temperature_unit": "celsius",
        "timezone": "auto",
    }

    r = requests.get(url, params=params, timeout=timeout_s)
    r.raise_for_status()
    data = r.json()

    cw = data.get("current_weather") or {}
    code = cw.get("weathercode")
    temp_c = cw.get("temperature")

    # Pick hourly values at the current time
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    pop_list = hourly.get("precipitation_probability") or []
    feels_list = hourly.get("apparent_temperature") or []

    # current_weather.time is like "2026-02-17T02:00"
    cur_time = cw.get("time")
    pop_pct: Optional[int] = None
    feels_like_c: Optional[float] = None

    if cur_time and times:
        idx = _nearest_hour_index(times, cur_time)
        if 0 <= idx < len(pop_list):
            try:
                pop_pct = int(pop_list[idx]) if pop_list[idx] is not None else None
            except Exception:
                pop_pct = None
        if 0 <= idx < len(feels_list):
            try:
                feels_like_c = float(feels_list[idx]) if feels_list[idx] is not None else None
            except Exception:
                feels_like_c = None

    condition_text, condition_kind = _map_weathercode(code)

    return WeatherSnapshot(
        condition_text=condition_text,
        condition_kind=condition_kind,
        pop_pct=pop_pct,
        temp_c=float(temp_c) if temp_c is not None else None,
        feels_like_c=feels_like_c,
        updated_at=time.time(),
    )


def c_to_f(c: Optional[float]) -> Optional[float]:
    if c is None:
        return None
    return (c * 9.0 / 5.0) + 32.0


class WeatherWorker:
    """
    Background updater so UI never blocks.
    Call start(), then use get_snapshot() anytime.
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        refresh_s: int = 600,  # 10 minutes
    ):
        self.lat = lat
        self.lon = lon
        self.refresh_s = refresh_s

        self._lock = threading.Lock()
        self._snap = WeatherSnapshot(
            condition_text="-",
            condition_kind="cloudy",
            pop_pct=None,
            temp_c=None,
            feels_like_c=None,
            updated_at=0.0,
        )

        self._stop = threading.Event()
        self._th: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._th and self._th.is_alive():
            return
        self._stop.clear()
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()

    def stop(self) -> None:
        self._stop.set()

    def get_snapshot(self) -> WeatherSnapshot:
        with self._lock:
            return self._snap

    def force_refresh(self) -> None:
        # do a one-shot refresh in a thread (doesn't block caller)
        threading.Thread(target=self._refresh_once, daemon=True).start()

    def _run(self) -> None:
        # initial fetch
        self._refresh_once()
        while not self._stop.wait(self.refresh_s):
            self._refresh_once()

    def _refresh_once(self) -> None:
        try:
            snap = fetch_weather_open_meteo(self.lat, self.lon)
            with self._lock:
                self._snap = snap
        except Exception:
            # keep last snapshot on error
            pass
