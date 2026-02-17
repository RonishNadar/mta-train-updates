# mta_app/runner.py
from __future__ import annotations

import time

import requests

from mta_app.formatter import format_arrivals
from mta_app.mta_client import extract_arrivals, fetch_feed
from mta_app.models import Settings, StationConfig


def _station_run_for_sec(st: StationConfig, app_run_for_sec: int) -> int:
    # station override if > 0, otherwise inherit from app
    return st.run_for_sec if st.run_for_sec > 0 else app_run_for_sec


def run_monitor(settings: Settings) -> None:
    app = settings.app

    print(f"Polling interval: {app.poll_interval_sec}s")
    if app.run_for_sec == 0:
        print("Run duration: infinite (Ctrl+C to stop)")
    else:
        print(f"Run duration: {app.run_for_sec}s")
    print("")

    # Per-station end-times (0 means infinite for that station)
    station_end_times = {}
    now = time.time()
    for st in settings.stations:
        dur = _station_run_for_sec(st, app.run_for_sec)
        station_end_times[st.stop_name] = (0 if dur == 0 else now + dur)

    try:
        while True:
            cycle_start = time.time()

            # If the app has a finite duration, stop when all stations have ended
            active = 0
            for st in settings.stations:
                end_t = station_end_times[st.stop_name]
                if end_t == 0 or time.time() < end_t:
                    active += 1
            if active == 0:
                print("All station timers completed. Exiting.")
                return

            for st in settings.stations:
                end_t = station_end_times[st.stop_name]
                if end_t != 0 and time.time() >= end_t:
                    continue  # station finished
                _print_station_once(st, settings)

            # Sleep until the next poll boundary
            elapsed = time.time() - cycle_start
            sleep_s = max(0.0, float(app.poll_interval_sec) - elapsed)
            time.sleep(sleep_s)

    except KeyboardInterrupt:
        print("\nStopped by user.")


def _print_station_once(st: StationConfig, settings: Settings) -> None:
    app = settings.app
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    print("--------------------------------")
    print(f"{ts} | {st.stop_name} ({st.direction_label})")

    rt_stop_id = st.rt_stop_id  # gtfs_stop_id + direction (e.g., N03 + N -> N03N)
    print(
        f"feed={st.feed} gtfs_stop_id={st.gtfs_stop_id} "
        f"direction={st.direction} rt_stop_id={rt_stop_id}"
    )

    try:
        msg = fetch_feed(st.feed, timeout_s=app.http_timeout_sec)
        arrivals = extract_arrivals(msg, rt_stop_id)
        print(format_arrivals(arrivals, limit=app.print_limit))
    except requests.RequestException as e:
        print(f"Fetch error: {e}")
    except Exception as e:
        print(f"Error: {e}")
