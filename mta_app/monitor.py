from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

from mta_app.mta_client import extract_arrivals, fetch_feed
from mta_app.models import Settings, StationConfig


@dataclass
class StationSnapshot:
    # [(route_id, eta_min), ...] length 0..print_limit
    arrivals: List[Tuple[str, Optional[int]]]
    last_ok_ts: float
    last_error: str


class Monitor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._snapshots: Dict[int, StationSnapshot] = {}
        self._stop = threading.Event()
        self._force_refresh = threading.Event()

        # index stations by feed to reduce fetches
        self._stations_by_feed: Dict[str, List[Tuple[int, StationConfig]]] = {}
        for idx, st in enumerate(settings.stations):
            self._stations_by_feed.setdefault(st.feed, []).append((idx, st))

        # init empty snapshots
        for i in range(len(settings.stations)):
            self._snapshots[i] = StationSnapshot(arrivals=[], last_ok_ts=0.0, last_error="")

        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._force_refresh.set()
        self._thread.join(timeout=2.0)

    def force_refresh(self) -> None:
        self._force_refresh.set()

    def get_snapshot(self, station_index: int) -> StationSnapshot:
        with self._lock:
            return self._snapshots[station_index]

    def _run(self) -> None:
        poll = float(self.settings.app.poll_interval_sec)
        timeout = int(self.settings.app.http_timeout_sec)

        while not self._stop.is_set():
            cycle_start = time.time()
            try:
                self._poll_once(timeout)
            except Exception:
                # keep thread alive no matter what
                pass

            # wait for next cycle OR forced refresh OR stop
            while True:
                if self._stop.is_set():
                    return
                if self._force_refresh.is_set():
                    self._force_refresh.clear()
                    break
                elapsed = time.time() - cycle_start
                remaining = poll - elapsed
                if remaining <= 0:
                    break
                time.sleep(min(0.2, remaining))

    def _poll_once(self, timeout_s: int) -> None:
        # fetch each feed once, apply to all stations in that feed
        for feed, items in self._stations_by_feed.items():
            if self._stop.is_set():
                return
            try:
                msg = fetch_feed(feed, timeout_s=timeout_s)
                now = int(time.time())
                for idx, st in items:
                    arr = extract_arrivals(msg, st.rt_stop_id, now=now)

                    limit = int(self.settings.app.print_limit)
                    if limit <= 0:
                        limit = 2  # safety fallback

                    top = [(a.route_id, a.eta_min) for a in arr[:limit]]

                    with self._lock:
                        self._snapshots[idx] = StationSnapshot(
                            arrivals=top,
                            last_ok_ts=time.time(),
                            last_error="",
                        )
            except requests.RequestException as e:
                err = f"Fetch error: {e}"
                with self._lock:
                    for idx, _ in items:
                        snap = self._snapshots[idx]
                        self._snapshots[idx] = StationSnapshot(
                            arrivals=snap.arrivals,
                            last_ok_ts=snap.last_ok_ts,
                            last_error=err,
                        )
