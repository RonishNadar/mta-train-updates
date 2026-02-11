from __future__ import annotations
import time
from typing import List, Optional

import requests
from google.transit import gtfs_realtime_pb2

from mta_app.feeds import FEEDS
from mta_app.models import Arrival


def fetch_feed(feed_name: str, timeout_s: int) -> gtfs_realtime_pb2.FeedMessage:
    url = FEEDS[feed_name]
    r = requests.get(url, timeout=timeout_s)
    r.raise_for_status()

    msg = gtfs_realtime_pb2.FeedMessage()
    msg.ParseFromString(r.content)
    return msg


def extract_arrivals(
    msg: gtfs_realtime_pb2.FeedMessage,
    stop_id: str,
    now: Optional[int] = None,
) -> List[Arrival]:
    now = int(time.time()) if now is None else now
    out: List[Arrival] = []

    for ent in msg.entity:
        if not ent.HasField("trip_update"):
            continue

        tu = ent.trip_update
        route_id = tu.trip.route_id if tu.HasField("trip") else ""
        trip_id = tu.trip.trip_id if tu.HasField("trip") else ""

        for stu in tu.stop_time_update:
            if stu.stop_id != stop_id:
                continue

            eta = None
            if stu.HasField("arrival") and stu.arrival.time:
                eta = int(stu.arrival.time)
            elif stu.HasField("departure") and stu.departure.time:
                eta = int(stu.departure.time)

            if eta is None:
                continue
            if eta < now - 30:  # ignore stale
                continue

            out.append(
                Arrival(
                    route_id=route_id or "?",
                    trip_id=trip_id or "",
                    eta_epoch=eta,
                    eta_min=max(0, int(round((eta - now) / 60.0))),
                )
            )

    out.sort(key=lambda a: a.eta_epoch)
    return out
