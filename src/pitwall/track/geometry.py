"""Plane geometry for track outlines: arc-length resampling and loop smoothing."""

import bisect
import itertools
import math
from collections.abc import Sequence

Point = tuple[float, float]

# Tuned on Monza 2024 lap 39; see docs/design/track.md
CIRCUIT_POINTS = 500  # ~11.5 m spacing on a 5.8 km lap
SMOOTH_WINDOW = 3  # max shift 2.3 m; 5 gives 5.5 m on a ~12 m wide track


def path_length(points: Sequence[Point]) -> float:
    return sum(math.dist(a, b) for a, b in itertools.pairwise(points))


def resample(points: Sequence[Point], n: int, *, closed: bool) -> list[Point]:
    """n points evenly spaced by distance along the path.

    closed: the path is a loop; the gap from the last point back to the first counts,
    and the result does not repeat the first point. Open paths keep both endpoints.
    """
    if n < 2:
        raise ValueError(f"n must be at least 2, got {n}")
    if len(points) < (3 if closed else 2):
        raise ValueError(f"too few points for a {'closed' if closed else 'open'} path")
    path = [*points, points[0]] if closed else list(points)
    cumulative = list(
        itertools.accumulate((math.dist(a, b) for a, b in itertools.pairwise(path)), initial=0.0)
    )
    total = cumulative[-1]
    if total == 0:
        raise ValueError("path has zero length")
    step = total / n if closed else total / (n - 1)  # a loop has n gaps, an open path n - 1
    out: list[Point] = []
    for k in range(n):
        d = k * step
        # segment i runs from path[i] to path[i + 1] and contains distance d
        i = min(bisect.bisect_right(cumulative, d) - 1, len(path) - 2)
        seg = cumulative[i + 1] - cumulative[i]
        t = 0.0 if seg == 0 else (d - cumulative[i]) / seg  # repeated sample: zero-length segment
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return out


def smooth_loop(points: Sequence[Point], window: int) -> list[Point]:
    """Moving average over a closed loop: the window wraps around the start/finish line."""
    if window < 1 or window % 2 == 0:
        raise ValueError(f"window must be a positive odd number, got {window}")
    n = len(points)
    if window > n:
        raise ValueError(f"window {window} is longer than the loop ({n} points)")
    half = window // 2
    out: list[Point] = []
    for i in range(n):
        near = [points[(i + k) % n] for k in range(-half, half + 1)]
        out.append((sum(p[0] for p in near) / window, sum(p[1] for p in near) / window))
    return out
