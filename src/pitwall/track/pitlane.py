"""The pit lane path: the stretch where a pitting car leaves the circuit outline."""

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

from pitwall.ingest.openf1 import Lap, LocationSample
from pitwall.track.geometry import LoopIndex, Point
from pitwall.track.laps import pit_stops, span_samples

# Decimetres. Racing laps stay within 3m of the outline; Monza's pit lane runs 13-19m from it
PIT_OFFSET = 50.0
PIT_POINTS = 100  # ~7 m spacing on ~700 m pit path
# ~5 s at ~4 Hz. Real stops run 101-142 samples (Monza, Singapore, Las Vegas); one stray
# sample must not count as a pit lane
MIN_PIT_RUN = 20


@dataclass(frozen=True)
class PitStop:
    samples: Sequence[LocationSample]  # the in-lap then the out-lap
    lane: Sequence[Point]  # as driven, before resampling


def pit_stop(
    laps: Sequence[Lap], samples: Sequence[LocationSample], circuit: Sequence[Point]
) -> PitStop | None:
    """The first pit stop that gives a clear pit lane path; None if none does."""
    for in_lap, out_lap in pit_stops(laps):
        stop = span_samples(in_lap, out_lap, samples)
        lane = pit_lane([(s.x, s.y) for s in stop], circuit)
        if lane is not None:
            return PitStop(stop, lane)
    return None


def pit_lane(
    points: Sequence[Point],
    circuit: Sequence[Point],
    offset: float = PIT_OFFSET,
    min_run: int = MIN_PIT_RUN,
) -> list[Point] | None:
    """The pit lane, as driven: the longest run of points farther than offset from the circuit.

    points: one car's in-lap then out-lap, in time order. Both ends are joined onto the
    circuit, so the path branches off and rejoins it. None if the car never left the circuit
    for at least min_run points in a row
    """
    if offset <= 0:
        raise ValueError(f"offset must be positive, got {offset}")
    if min_run < 1:
        raise ValueError(f"min_run must be at least 1, got {min_run}")
    index = LoopIndex(circuit)
    far = [math.dist(p, index.nearest(p)) > offset for p in points]
    run = _longest_run(far)
    if run is None or run[1] - run[0] < min_run:
        return None
    start, stop = run
    # the samples either side of the run are where the car left and rejoined the circuit
    entry = points[start - 1] if start > 0 else points[start]
    exit_ = points[stop] if stop < len(points) else points[stop - 1]
    return [index.nearest(entry), *points[start:stop], index.nearest(exit_)]


def _longest_run(flags: Sequence[bool]) -> tuple[int, int] | None:
    """[start, stop) of the longest run of True; None if there is none."""
    best: tuple[int, int] | None = None
    for flag, group in itertools.groupby(enumerate(flags), key=lambda pair: pair[1]):
        indices = [i for i, _ in group]
        if flag and (best is None or len(indices) > best[1] - best[0]):
            best = (indices[0], indices[-1] + 1)
    return best
