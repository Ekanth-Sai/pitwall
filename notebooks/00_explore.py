"""Phase 0 exploration: Pull one race from OpenF1 and draw the circuit"""

import itertools
import statistics
from collections.abc import Sequence
from datetime import UTC, timedelta
from pathlib import Path

import matplotlib.pyplot as plt

from pitwall.ingest.openf1 import BASE_URL, OpenF1Client
from pitwall.ingest.transport import CachedTransport, HttpTransport
from pitwall.track.geometry import Point, path_length, rotate
from pitwall.track.laps import last_lap_end
from pitwall.track.outline import TrackOutline

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "openf1"
CAR = 16  # Leclerc


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
        laps = client.laps(session.key, driver=CAR)

        # session.end is the scheduled end; the car's last lap is when it actually stopped
        end = last_lap_end(laps)
        if end is None:
            raise SystemExit(f"No timed laps for car {CAR}")
        print(f"fetching car {CAR} locations up to {end} (scheduled end {session.end})")
        trace = client.locations(session.key, session.start, end, driver=CAR)
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

    track = TrackOutline.build(laps, trace)
    loop = [*track.circuit, track.circuit[0]]

    print(
        f"circuit: {len(track.circuit)} points, {path_length(loop) / 10_000:.3f} km; "
        f"rotation {track.rotation} deg; outline JSON {len(track.to_json()) / 1000:.1f} kB"
    )

    def draw(points: Sequence[Point], style: str = "-") -> None:
        # turned by track.rotation, like the frontend will
        turned = [rotate(p, track.rotation) for p in points]
        ax.plot([x for x, _ in turned], [y for _, y in turned], style, color="lightgrey", lw=1)

    _fig, ax = plt.subplots(figsize=(12, 6))
    draw(loop)
    if track.pit_lane is not None:
        print(f"pit lane: {len(track.pit_lane)} points, {path_length(track.pit_lane) / 10:.0f} m")
        draw(track.pit_lane, "--")

    # window is sorted by time, so the last one wins
    latest = {s.driver: s for s in window if s.on_track}
    for num, s in latest.items():
        driver = drivers.get(num)
        colour = "#" + (driver.team_colour if driver and driver.team_colour else "888888")
        x, y = rotate((s.x, s.y), track.rotation)
        ax.scatter(x, y, s=220, color=colour, edgecolor="black", zorder=2)
        ax.text(
            x,
            y,
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
