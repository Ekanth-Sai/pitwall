"""Phase 0 exploration: Pull one race from OpenF1 and draw the circuit"""

import hashlib
import itertools
import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import matplotlib.pyplot as plt

BASE = "https://api.openf1.org/v1/"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "openf1"
CHUNK = timedelta(minutes=10)

Params = dict[str, str | int]
Row = dict[str, Any]


def fetch(endpoint: str, params: Params) -> list[Row]:
    """Get an OpenF1 endpoint once, then serve it from disk"""
    key = json.dumps(params, sort_keys=True)
    digest = hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:16]
    out = CACHE / endpoint / f"{digest}.json"
    if out.exists():
        rows: list[Row] = json.loads(out.read_text(encoding="utf-8"))
        return rows

    r = httpx.get(BASE + endpoint, params=params, timeout=60)
    if r.status_code == 404:  # OpenF1 answers "no rows" with 404, not []
        rows = []
    else:
        r.raise_for_status()
        rows = r.json()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def fmt(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def parse_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def fetch_location(
    session_key: int, start: datetime, end: datetime, driver: int | None = None
) -> list[Row]:
    """Fetch location rows in CHUNK-sized windows (big queries are slow server-side)"""
    rows: list[Row] = []
    t = start
    while t < end:
        params: Params = {
            "session_key": session_key,
            "date>": fmt(t),
            "date<": fmt(min(t + CHUNK, end)),
        }
        if driver is not None:
            params["driver_number"] = driver
        chunk = fetch("location", params)
        print(f"{fmt(t)} {len(chunk):>5} rows")
        rows.extend(chunk)
        t += CHUNK

    # window edges are inclusive, so a sample on a boundary can appear twice
    unique = {(r["date"], r["driver_number"]): r for r in rows}
    return sorted(unique.values(), key=lambda r: r["date"])


def main() -> None:
    # Find the session
    sessions = fetch(
        "sessions", {"year": 2024, "circuit_short_name": "Monza", "session_name": "Race"}
    )
    if not sessions:
        raise SystemExit("No Monza 2024 race found in OpenF1")
    session = sessions[0]
    key = session["session_key"]
    start, end = parse_utc(session["date_start"]), parse_utc(session["date_end"])
    print(f"session {key}: {session['location']} {start} -> {end}")

    # drivers (team colours, numbers, acronyms)
    drivers = {d["driver_number"]: d for d in fetch("drivers", {"session_key": key})}

    # one car's whole race trace = the circuit outline
    car = 16
    print(f"fetching car {car} locations: ")
    trace = fetch_location(key, start, end, driver=car)
    if not trace:
        raise SystemExit(f"No location data for car {car}")

    times = [parse_utc(r["date"]) for r in trace]
    gaps = [(b - a).total_seconds() for a, b in itertools.pairwise(times)]
    print(f"car {car}: {len(trace)} samples, {times[0]} -> {times[-1]}")
    print(
        f"sample interval: median {statistics.median(gaps):.3f}s, "
        f"max {max(gaps):.1f}s gaps > 1s: {sum(g > 1 for g in gaps)}"
    )

    xs = [r["x"] for r in trace if (r["x"], r["y"]) != (0, 0)]
    ys = [r["y"] for r in trace if (r["x"], r["y"]) != (0, 0)]

    _fig, ax = plt.subplots(figsize=(9, 9))
    ax.plot(xs, ys, color="lightgrey", linewidth=1, zorder=1)

    # all cars at one moment, team colour + number
    snap = start + timedelta(minutes=40)
    window = fetch(
        "location",
        {"session_key": key, "date>": fmt(snap), "date<": fmt(snap + timedelta(seconds=2))},
    )
    latest: dict[int, Row] = {}
    for r in sorted(window, key=lambda r: r["date"]):
        latest[r["driver_number"]] = r

    for num, r in latest.items():
        colour = "#" + (drivers.get(num, {}).get("team_colour") or "888888")
        ax.scatter(r["x"], r["y"], s=220, color=colour, edgecolor="black", zorder=2)
        ax.text(
            r["x"],
            r["y"],
            str(num),
            ha="center",
            va="center",
            fontsize=7,
            color="white",
            weight="bold",
            zorder=3,
        )

    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{session['location']} {session['year']} - {fmt(snap)} UTC")
    plt.show()


if __name__ == "__main__":
    main()
