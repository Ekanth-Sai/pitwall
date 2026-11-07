"""Figures for docs/design/track.md: OpenF1's axes, the outline against the raw lap, the pit lane.

Run from the repo root: uv run python scripts/figures/track.py
"""

import itertools
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from matplotlib.axes import Axes
from matplotlib.figure import Figure

from pitwall.ingest.openf1 import BASE_URL, Lap, LocationSample, OpenF1Client
from pitwall.ingest.transport import CachedTransport, HttpTransport
from pitwall.track.geometry import Bounds, LoopIndex, Point, rotate
from pitwall.track.laps import lap_samples, last_lap_end, representative_lap
from pitwall.track.outline import TrackOutline
from pitwall.track.pitlane import PIT_OFFSET, pit_stop

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "openf1"
OUT = ROOT / "docs" / "figures"
CAR = 16  # Leclerc at Monza 2024: every number in track.md comes from this car

TRACK = "#b0b0b0"
RAW = "#d1495b"
PIT = "#00798c"


def fetch() -> tuple[list[Lap], list[LocationSample]]:
    with HttpTransport.create(BASE_URL) as http:
        client = OpenF1Client(CachedTransport(http, CACHE))
        sessions = client.sessions(2024, "Monza", "Race")
        if not sessions:
            raise SystemExit("No Monza 2024 race found in OpenF1")
        session = sessions[0]
        laps = client.laps(session.key, driver=CAR)
        end = last_lap_end(laps)
        if end is None:
            raise SystemExit(f"No timed laps for car {CAR}")
        return laps, client.locations(session.key, session.start, end, driver=CAR)


def xy(samples: Sequence[LocationSample]) -> list[Point]:
    return [(s.x, s.y) for s in samples]


class Plotter:
    """Draws in the outline's rotated frame, in metres, as the frontend will show it."""

    def __init__(self, track: TrackOutline) -> None:
        self.track = track

    def turn(self, points: Sequence[Point]) -> tuple[list[float], list[float]]:
        turned = [rotate(p, self.track.rotation) for p in points]
        return [x / 10 for x, _ in turned], [y / 10 for _, y in turned]

    def line(self, ax: Axes, points: Sequence[Point], **style: Any) -> None:
        ax.plot(*self.turn(points), **style)

    def dots(self, ax: Axes, points: Sequence[Point], **style: Any) -> None:
        ax.scatter(*self.turn(points), **style)

    def circuit(self, ax: Axes, **style: Any) -> None:
        self.line(ax, [*self.track.circuit, self.track.circuit[0]], **style)

    def box(self, points: Sequence[Point], margin: float) -> Bounds:
        """A zoom window in plot units (metres) around points in OpenF1 units."""
        b = Bounds.of(zip(*self.turn(points), strict=True))
        return Bounds(b.min_x - margin, b.min_y - margin, b.max_x + margin, b.max_y + margin)


def zoom(ax: Axes, box: Bounds, at: tuple[float, float, float, float]) -> Axes:
    """An inset placed at `at` (fractions of ax) showing box, with lines to where it is."""
    inset = ax.inset_axes(at, xlim=(box.min_x, box.max_x), ylim=(box.min_y, box.max_y))
    inset.set_xticks([])
    inset.set_yticks([])
    ax.indicate_inset_zoom(inset, edgecolor="black")
    return inset


def bare(ax: Axes) -> None:
    """A map, not a chart: equal scale, no axes."""
    ax.set_aspect("equal")
    ax.set_axis_off()


def room_below(ax: Axes, share: float) -> tuple[float, float, float, float]:
    """Empty space under the map, `share` of the axes high, so an inset covers no track."""
    low, high = ax.get_ylim()
    ax.set_ylim(low - (high - low) * share / (1 - share), high)
    return (0.25, 0.0, 0.5, share)


def axes_figure(track: TrackOutline, lap: Lap, raw: Sequence[Point]) -> Figure:
    """OpenF1's own frame, before any turning: where (0, 0) is, and what a lap's first steps are."""
    fig = Figure(figsize=(11, 7), layout="constrained")
    whole, steps = fig.subplots(1, 2, width_ratios=(1, 1.15))

    circuit = [*track.circuit, track.circuit[0]]
    whole.plot(*zip(*circuit, strict=True), color=TRACK, lw=2, label="circuit")
    if track.pit_lane is not None:
        whole.plot(*zip(*track.pit_lane, strict=True), color=PIT, lw=1, ls="--", label="pit lane")
    whole.axhline(0, color="black", lw=0.8)
    whole.axvline(0, color="black", lw=0.8)
    origin_gap = min(math.dist((0, 0), p) for p in track.circuit) / 10
    whole.scatter(
        [0], [0], s=40, color=RAW, zorder=3, label=f"(0, 0): {origin_gap:.0f} m off the track"
    )
    (x0, y0), (x3, y3) = raw[0], raw[3]
    whole.scatter([x0], [y0], s=30, color="black", zorder=3, label=f"p0 = ({x0:g}, {y0:g})")
    # an arrow along the way the car is going, stretched to be seen at this scale
    whole.annotate("", xy=(x3, y3 + 2500), xytext=(x0, y0), arrowprops={"arrowstyle": "->"})
    whole.set_aspect("equal")
    whole.set_xlabel("x (dm), grows to the right")
    whole.set_ylabel("y (dm), grows up")
    whole.legend(loc="upper left", fontsize=8, frameon=False)
    whole.set_title("Monza in OpenF1's axes, before turning")

    first = raw[:6]
    steps.plot(*zip(*first, strict=True), color=TRACK, lw=1, zorder=1)
    steps.scatter(*zip(*first, strict=True), s=30, color="black", zorder=3)
    for i, (x, y) in enumerate(first):
        right = 40 if i == 0 else 8  # p0's label goes past the triangle
        steps.annotate(
            f"p{i} = ({x:g}, {y:g})", (x, y), xytext=(right, -4), textcoords="offset points"
        )
    (px, py), (qx, qy) = first[0], first[1]
    steps.plot([px, qx, qx], [py, py, qy], color=RAW, lw=1, ls="--")
    steps.annotate(
        f"dx = {qx - px:g}",
        ((px + qx) / 2, py),
        xytext=(0, -14),
        textcoords="offset points",
        ha="center",
        color=RAW,
    )
    steps.annotate(
        f"dy = {qy - py:g}",
        (qx, (py + qy) / 2),
        xytext=(6, 0),
        textcoords="offset points",
        color=RAW,
    )
    steps.set_xlim(first[0][0] - 10, first[-1][0] + 60)  # room for the labels
    steps.set_xlabel("x (dm): note the scale, x is stretched next to y")
    steps.set_ylabel("y (dm)")
    steps.spines[["top", "right"]].set_visible(False)
    steps.set_title(f"Lap {lap.number}'s first {len(first)} samples, and the step p0 to p1")
    return fig


def outline_figure(plot: Plotter, lap: Lap, raw: Sequence[Point]) -> Figure:
    fig = Figure(figsize=(10, 7), layout="constrained")  # no pyplot: no window, no global state
    ax = fig.subplots()
    plot.circuit(ax, color="black", lw=0.8, label=f"outline ({len(plot.track.circuit)} points)")
    plot.dots(ax, raw, s=4, color=RAW, zorder=2, label=f"lap {lap.number} samples ({len(raw)})")

    # the closest pair of samples is where the car is slowest: the first chicane at Monza
    slowest = min(itertools.pairwise(raw), key=lambda pair: math.dist(*pair))[0]
    chicane = [p for p in raw if math.dist(p, slowest) < 800]  # within 80 m
    inset = zoom(ax, plot.box(chicane, margin=10), room_below(ax, 0.35))
    inset.set_aspect("equal")
    plot.circuit(inset, color="black", lw=0.8, marker="o", ms=2.5, label="outline points")
    plot.dots(inset, raw, s=22, facecolor="none", edgecolor=RAW, zorder=2, label="samples")
    inset.legend(loc="upper left", fontsize=7, frameon=False)

    bare(ax)
    ax.legend(loc="upper left", frameon=False)
    ax.set_title("Circuit outline: one racing lap, resampled to 500 points and smoothed")
    return fig


def pit_figure(plot: Plotter, stop: Sequence[LocationSample]) -> Figure:
    lane = plot.track.pit_lane
    if lane is None:
        raise SystemExit("the outline has no pit lane to draw")
    points = xy(stop)
    circuit = LoopIndex(plot.track.circuit)
    metres = [math.dist(p, circuit.nearest(p)) / 10 for p in points]
    seconds = [(s.time - stop[0].time).total_seconds() for s in stop]
    threshold = PIT_OFFSET / 10

    fig = Figure(figsize=(10, 10), layout="constrained")
    top, bottom = fig.subplots(2, 1, height_ratios=(2.4, 1))
    plot.circuit(top, color=TRACK, lw=1.2, label="circuit")
    plot.line(top, lane, color=PIT, lw=1.5, label=f"pit lane ({len(lane)} points)")

    # zoom where the lane is farthest from the track
    farthest = points[max(range(len(points)), key=metres.__getitem__)]
    stretch = [p for p in lane if math.dist(p, farthest) < 1000]  # within 100 m
    inset = zoom(top, plot.box(stretch, margin=10), room_below(top, 0.35))
    inset.set_aspect("equal")
    plot.circuit(inset, color=TRACK, lw=1.2)
    plot.line(inset, lane, color=PIT, lw=1.5)
    plot.dots(inset, points, s=8, color=RAW, zorder=3, label="in-lap and out-lap samples")
    inset.legend(loc="upper left", fontsize=7, frameon=False)

    bare(top)
    top.legend(loc="upper left", frameon=False)
    top.set_title(
        f"Pit lane: where the pitting car runs more than {threshold:g} m from the circuit"
    )

    bottom.plot(seconds, metres, color=RAW, lw=1, label="distance to the circuit")
    bottom.axhline(threshold, color=PIT, ls="--", lw=1, label=f"threshold, {threshold:g} m")
    bottom.fill_between(
        seconds, 0, metres, where=[m > threshold for m in metres], color=PIT, alpha=0.15
    )
    bottom.set_xlabel("seconds from the start of the in-lap to the end of the out-lap")
    bottom.set_ylabel("metres")
    bottom.spines[["top", "right"]].set_visible(False)
    bottom.legend(loc="upper left", frameon=False)
    return fig


def main() -> None:
    laps, samples = fetch()
    track = TrackOutline.build(laps, samples)
    plot = Plotter(track)

    lap = representative_lap(laps)
    stop = pit_stop(laps, samples, track.circuit)  # the stop the pit lane was drawn from
    if lap is None or stop is None:
        raise SystemExit(f"car {CAR} needs a racing lap and a pit stop")
    raw = xy(lap_samples(lap, samples))
    figures = {
        "track_axes.png": axes_figure(track, lap, raw),
        "track_outline.png": outline_figure(plot, lap, raw),
        "track_pit_lane.png": pit_figure(plot, stop.samples),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    for name, fig in figures.items():
        # no "Software" tag: a matplotlib upgrade alone shouldn't rewrite the PNGs
        fig.savefig(OUT / name, dpi=150, metadata={"Software": None})
        print(f"wrote {(OUT / name).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
