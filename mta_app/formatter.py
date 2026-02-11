from __future__ import annotations
from typing import List
from mta_app.models import Arrival


def format_arrivals(arrivals: List[Arrival], limit: int) -> str:
    if not arrivals:
        return "No upcoming arrivals found (stop_id mismatch or no predictions)."

    limit = max(1, min(limit, 25))
    lines = []
    for a in arrivals[:limit]:
        # lines.append(f"  Route {a.route_id:>3}  in {a.eta_min:>2} min   (eta_epoch={a.eta_epoch})")
        lines.append(f"  Route {a.route_id:>3}  in {a.eta_min:>2} min")
    return "\n".join(lines)
