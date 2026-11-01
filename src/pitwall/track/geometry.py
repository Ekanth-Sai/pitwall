"""Plane geometry for track outlines: arc-length resampling and loop smoothing."""

import bisect
import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Self

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


def nearest_on_loop(p: Point, loop: Sequence[Point]) -> Point:
    """The point on the closed polyline through loop that is closest to p."""
    if not loop:
        raise ValueError("loop is empty")
    segments = zip(loop, [*loop[1:], loop[0]], strict=True)
    return min((_nearest_on_segment(p, a, b) for a, b in segments), key=lambda q: math.dist(p, q))


def _nearest_on_segment(p: Point, a: Point, b: Point) -> Point:
    # project p onto the line through a and b, then clamp to the segment
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return (ax + t * dx, ay + t * dy)


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @classmethod
    def of(cls, points: Iterable[Point]) -> Self:
        pts = list(points)
        if not pts:
            raise ValueError("no points to bound")
        xs, ys = zip(*pts, strict=True)
        return cls(min(xs), min(ys), max(xs), max(ys))


def rotate(p: Point, degrees: float) -> Point:
    """Rotate p counter-clockwise about the origin."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    x, y = p
    return (x * c - y * s, x * s + y * c)


def principal_angle(points: Sequence[Point]) -> float:
    """Direction of the points' long axis, in degrees from the x axis, in (-90, 90]."""
    n = len(points)
    if n < 2:
        raise ValueError(f"need at least 2 points, got {n}")
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    syy = sum((y - my) ** 2 for _, y in points)
    sxy = sum((x - mx) * (y - my) for x, y in points)
    # the angle of the covariance matrix's main eigenvector
    return math.degrees(0.5 * math.atan2(2 * sxy, sxx - syy))
