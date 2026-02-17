import pandas as pd
import json

CSV_PATH = "MTA_Subway_Stations_20260217.csv"


def make_entry(stop_name_query: str, route_letter: str, direction: str):
    df = pd.read_csv(CSV_PATH)
    direction = direction.upper()
    route_letter = route_letter.upper()

    rows = df[df["Stop Name"].str.contains(stop_name_query, case=False, na=False)]
    rows = rows[rows["Daytime Routes"].astype(str).str.contains(route_letter, na=False)]

    if rows.empty:
        raise SystemExit("No match found. Try a different name or route letter.")

    r = rows.iloc[0]
    gtfs_id = r["GTFS Stop ID"]
    dir_label = (
        r["North Direction Label"] if direction == "N" else r["South Direction Label"]
    )

    entry = {
        "stop_name": f"{r['Stop Name']} ({route_letter})",
        "gtfs_stop_id": gtfs_id,
        "direction": direction,
        "direction_label": str(dir_label),
        "feed": "NQRW" if route_letter in ("N", "Q", "R", "W") else "UNKNOWN",
        "run_for_sec": 0,
    }
    print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    # Example: Fort Hamilton Pkwy, N train, northbound
    make_entry("Fort Hamilton Pkwy", "N", "N")
