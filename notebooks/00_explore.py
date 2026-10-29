"""Phase 0 exploration: Pull one race from OpenF1 and draw the circuit"""

import itertools
import statistics
from datetime import UTC, timedelta
from pathlib import Path

import matplotlib.pyplot as plt

from pitwall.ingest.openf1 import BASE_URL, LocationSample, OpenF1Client
from pitwall.ingest.transport import CachedTransport, HttpTransport

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "openf1"
CAR = 16  # Leclerc


def on_track(samples: list[LocationSample]) -> list[LocationSample]:
    """(0, 0) means 'no position' (car in the garage or before the start)"""
    return [s for s in samples if (s.x, s.y) != (0, 0)]


def main() -> None:
    with HttpTransport.create(BASE_URL) as http:
        client = OpenF1Client(CachedTransport(http, CACHE))

        # find the session
        sessions = client.sessions(2024, "Monza", "Race")
        if not sessions:
            raise SystemExit("No Monza 2024 race found in OpenF1")
        session = sessions[0]
        print(f"session {session.key}: {session.location} {session.start} -> {session.end}")

        # drivers (team colors, numbers, acronyms)
        drivers = {d.number: d for d in client.drivers(session.key)}

        # one car's whole race trace = the circuit outline
        print(f"fetching car {CAR} locations")
        trace = client.locations(session.key, session.start, session.end, driver=CAR)
        if len(trace) < 2:
            raise SystemExit(f"Need at least 2 location samples for car {CAR}, got {len(trace)}")

        # all cars at one moment
        snap = session.start + timedelta(minutes=40)
        window = client.locations(session.key, snap, snap + timedelta(seconds=2))

    gaps = [(b.time - a.time).total_seconds() for a, b in itertools.pairwise(trace)]
    print(f"car {CAR}: {len(trace)} samples, {trace[0].time} -> {trace[-1].time}")
    print(
        f"sample interval: median {statistics.median(gaps):.3f}s, "
        f"max {max(gaps):.1f}s, gaps > 1s: {sum(g > 1 for g in gaps)}"
    )

    outline = on_track(trace)
    _fig, ax = plt.subplots(figsize=(9, 9))
    ax.plot([s.x for s in outline], [s.y for s in outline], color="lightgrey", lw=1, zorder=1)

    # window is sorted by time, so the last one wins
    latest = {s.driver: s for s in on_track(window)}
    for num, s in latest.items():
        driver = drivers.get(num)
        colour = "#" + (driver.team_colour if driver and driver.team_colour else "888888")
        ax.scatter(s.x, s.y, s=220, color=colour, edgecolor="black", zorder=2)
        ax.text(
            s.x,
            s.y,
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
    ax.set_title(
        f"{session.location} {session.year} - {snap.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC"
    )
    plt.show()


if __name__ == "__main__":
    main()
