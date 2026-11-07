"""Figures for docs/phases/phase0.md: the whole field at one moment, and the gaps to the leader.

Run from the repo root: uv run python scripts/figures/phase0.py
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from matplotlib.figure import Figure
from track import Plotter, bare

from pitwall.ingest.openf1 import BASE_URL, Driver, LocationSample, OpenF1Client, Row
from pitwall.ingest.transport import CachedTransport, HttpTransport, PacedTransport
from pitwall.replay.colours import FALLBACK, ink_on
from pitwall.track.laps import last_lap_end
from pitwall.track.outline import TrackOutline

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "openf1"
OUT = ROOT / "docs" / "figures"
CAR = 16  # Leclerc: the outline comes from his laps, as in track.md
SNAPSHOT = timedelta(minutes=40)  # after the session start, as in the explore notebook
TRACK = "#b0b0b0"
CONTEXT = "#c8c8c8"
INK = "#2b6cb0"


@dataclass(frozen=True)
class Race:
    track: TrackOutline
    start: datetime
    snap: datetime
    field: list[LocationSample]  # every car, 2 s from snap
    drivers: dict[int, Driver]
    intervals: list[Row]
    positions: list[Row]


def fetch(client: OpenF1Client) -> Race:
    sessions = client.sessions(2024, "Monza", "Race")
    if not sessions:
        raise SystemExit("No Monza 2024 race found in OpenF1")
    session = sessions[0]
    laps = client.laps(session.key, driver=CAR)
    end = last_lap_end(laps)
    if not laps or end is None:
        raise SystemExit(f"No timed laps for car {CAR}")
    # lap 1 starts at the race start (race control: SESSION STARTED)
    start = min(laps, key=lambda lap: lap.number).start
    if start is None:
        raise SystemExit(f"Lap 1 of car {CAR} has no start time, so the race start is unknown")
    snap = session.start + SNAPSHOT
    return Race(
        track=TrackOutline.build(laps, client.locations(session.key, session.start, end, CAR)),
        start=start,
        snap=snap,
        field=client.locations(session.key, snap, snap + timedelta(seconds=2)),
        drivers={d.number: d for d in client.drivers(session.key)},
        intervals=client.query("intervals", {"session_key": session.key}),
        positions=client.query("position", {"session_key": session.key}),
    )


def field_figure(
    track: TrackOutline, field: list[LocationSample], drivers: dict[int, Driver], snap: datetime
) -> Figure:
    plot = Plotter(track)
    fig = Figure(figsize=(10, 5), layout="constrained")
    ax = fig.subplots()
    plot.circuit(ax, color=TRACK, lw=1.5)
    if track.pit_lane is not None:
        plot.line(ax, track.pit_lane, color=TRACK, lw=1, ls="--")

    latest = {s.driver: s for s in field if s.on_track}  # time order: the last sample wins
    teams: dict[str, str] = {}
    for number, sample in sorted(latest.items()):
        driver = drivers.get(number)
        colour = driver.team_colour if driver and driver.team_colour else FALLBACK
        if driver:
            teams.setdefault(driver.team, colour)
        (x,), (y,) = plot.turn([(sample.x, sample.y)])
        # a white ring keeps touching dots apart
        ax.scatter(x, y, s=240, color=f"#{colour}", edgecolor="white", lw=1.5, zorder=3)
        ax.text(
            x,
            y,
            str(number),
            ha="center",
            va="center",
            fontsize=7,
            weight="bold",
            color=ink_on(colour),
            zorder=4,
        )

    for team, colour in sorted(teams.items()):
        ax.scatter([], [], s=60, color=f"#{colour}", label=team)
    bare(ax)
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5), frameon=False, fontsize=8)
    ax.set_title(f"Monza 2024 race: {len(latest)} cars at {snap:%H:%M:%S} UTC, in team colours")
    return fig


def winner(positions: list[Row]) -> int:
    """The car in P1 at the end: the latest P1 row (a car that retired in P1 loses it later)."""
    leaders: list[tuple[datetime, int]] = [
        (datetime.fromisoformat(row["date"]), row["driver_number"])
        for row in positions
        if row["position"] == 1
    ]
    if not leaders:
        raise SystemExit("No car ever held P1 in the position feed")
    return max(leaders)[1]


def gaps_figure(
    intervals: list[Row], start: datetime, winner: int, drivers: dict[int, Driver]
) -> tuple[Figure, int]:
    """Gap to the leader over the race; also returns how many rows weren't a number of seconds."""
    lines: defaultdict[int, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
    skipped = 0
    # lines are drawn in row order, so sort by time rather than trust the feed's order
    timed = sorted(((datetime.fromisoformat(row["date"]), row) for row in intervals), key=_first)
    for at, row in timed:
        gap = row["gap_to_leader"]
        if at < start:
            continue  # formation and grid: an hour of rows before the race (openf1-data.md)
        if type(gap) not in (int, float):  # "+1 LAP" or null
            skipped += 1
            continue
        minutes, seconds = lines[row["driver_number"]]
        minutes.append((at - start).total_seconds() / 60)
        seconds.append(gap)

    if winner not in lines:
        raise SystemExit(f"No gap to the leader in seconds for the winner, car {winner}")

    fig = Figure(figsize=(10, 5), layout="constrained")
    ax = fig.subplots()
    for number, (minutes, seconds) in lines.items():
        if number != winner:
            ax.plot(minutes, seconds, color=CONTEXT, lw=1)
    minutes, seconds = lines[winner]
    ax.plot(minutes, seconds, color=INK, lw=2)
    name = drivers[winner].acronym if winner in drivers else str(winner)
    ax.annotate(
        f"{winner} {name}, the winner",
        (minutes[-1], seconds[-1]),
        xytext=(-4, 6),
        textcoords="offset points",
        ha="right",
        fontsize=9,
        color="#333333",
    )
    ax.set_xlabel("minutes since the race start")
    ax.set_ylabel("gap to the leader (s)")
    ax.set_title("Monza 2024 race: every car's gap to the leader (grey), the winner's in blue")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5", lw=0.8)
    ax.set_axisbelow(True)
    return fig, skipped


def _first(pair: tuple[datetime, Row]) -> datetime:
    return pair[0]


def main() -> None:
    with HttpTransport.create(BASE_URL) as http:
        race = fetch(OpenF1Client(CachedTransport(PacedTransport(http), CACHE)))
    lead = winner(race.positions)
    gaps, skipped = gaps_figure(race.intervals, race.start, lead, race.drivers)
    print(f"winner: car {lead}; gap rows that aren't seconds: {skipped}")
    figures = {
        "phase0_field.png": field_figure(race.track, race.field, race.drivers, race.snap),
        "phase0_gaps.png": gaps,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fig in figures.items():
        # no "Software" tag: a matplotlib upgrade alone shouldn't rewrite the PNGs
        fig.savefig(OUT / name, dpi=150, metadata={"Software": None})
        print(f"wrote {(OUT / name).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
