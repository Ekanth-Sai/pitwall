"""The pit lane path: the stretch where a pitting car leaves the circuit outline."""

import itertools
import math
from collections.abc import Sequence

from pitwall.track.geometry import Point, nearest_on_loop

# Decimetres. Racing laps stay within 3m of the outline; Monza's pit lane runs 13-19m from it
PIT_OFFSET = 50.0
PIT_POINTS = 100  # ~7 m spacing on ~700 m pit path


def pit_lane(
    points: Sequence[Point], circuit: Sequence[Point], offset: float = PIT_OFFSET
) -> list[Point] | None:
    """The pit lane, as driven: the longest run of points farther than offset from the circuit.

    points: one car's in-lap then out-lap, in time order. Both ends are joined onto the
    circuit, so the path branches off and rejoins it. None if the car never left the circuit.
    """
    if offset <= 0:
        raise ValueError(f"offset must be positive, got {offset}")
    far = [math.dist(p, nearest_on_loop(p, circuit)) > offset for p in points]
    run = _longest_run(far)
    if run is None:
        return None
    start, stop = run
    # the samples either side of the run are where the car left and rejoined the circuit
    entry = points[start - 1] if start > 0 else points[start]
    exit_ = points[stop] if stop < len(points) else points[stop - 1]
    return [nearest_on_loop(entry, circuit), *points[start:stop], nearest_on_loop(exit_, circuit)]


def _longest_run(flags: Sequence[bool]) -> tuple[int, int] | None:
    """[start, stop) of the longest run of True; None if there is none."""
    best: tuple[int, int] | None = None
    for flag, group in itertools.groupby(enumerate(flags), key=lambda pair: pair[1]):
        indices = [i for i, _ in group]
        if flag and (best is None or len(indices) > best[1] - best[0]):
            best = (indices[0], indices[-1] + 1)
    return best
