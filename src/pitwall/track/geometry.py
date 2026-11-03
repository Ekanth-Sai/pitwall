"""Plane geometry for track outlines: arc-length resampling and loop smoothing."""

import bisect
import itertools
import math
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
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


class LoopIndex:
    """nearest_on_loop for many points against one loop, without scanning every segment.

    A grid of square cells, each listing the segments that pass through it. A query scans
    rings of cells outwards from the point's cell. Anything outside ring r is at least r cells
    away, so it stops once the best distance found is no more than that. A query that meets
    more cells than there are segments (a point in a big empty area, such as the infield)
    projects the rest directly, so it never costs much more than nearest_on_loop.
    """

    def __init__(self, loop: Sequence[Point]) -> None:
        if not loop:
            raise ValueError("loop is empty")
        self._segments = list(zip(loop, [*loop[1:], loop[0]], strict=True))
        self._first = loop[0]
        bounds = Bounds.of(loop)
        self._origin = (bounds.min_x, bounds.min_y)
        # about one segment per cell; a loop of identical points still needs a cell size
        self._size = path_length([*loop, loop[0]]) / len(loop) or 1.0
        self._far = self._cell((bounds.max_x, bounds.max_y))  # the grid is (0, 0) to here
        self._cells: defaultdict[tuple[int, int], list[int]] = defaultdict(list)
        for i, (a, b) in enumerate(self._segments):
            for cell in self._cells_under(a, b):
                self._cells[cell].append(i)

    def nearest(self, p: Point) -> Point:
        """The point nearest_on_loop finds (or one as close, on a tie)."""
        cx, cy = self._cell(p)
        fx, fy = self._far
        # rings closer than `first` miss the grid (p is outside it); by `last` all of it is seen
        first = max(0, -cx, cx - fx, -cy, cy - fy)
        last = max(abs(cx), abs(cy), abs(fx - cx), abs(fy - cy))
        best, best_d = self._first, math.dist(p, self._first)
        seen: set[int] = set()
        scanned = 0
        for r in range(first, last + 1):
            ring = list(_ring(cx, cy, r, self._far))
            fresh = {i for cell in ring for i in self._cells.get(cell, ())} - seen
            best, best_d = self._closest(p, fresh, best, best_d)
            seen |= fresh
            if best_d <= r * self._size:
                return best
            scanned += len(ring)
            if scanned > len(self._segments):
                break  # mostly empty cells so far: projecting what's left is cheaper
        rest = set(range(len(self._segments))) - seen
        return self._closest(p, rest, best, best_d)[0]

    def _closest(
        self, p: Point, indices: Iterable[int], best: Point, best_d: float
    ) -> tuple[Point, float]:
        for i in indices:
            q = _nearest_on_segment(p, *self._segments[i])
            if (d := math.dist(p, q)) < best_d:
                best, best_d = q, d
        return best, best_d

    def _cells_under(self, a: Point, b: Point) -> set[tuple[int, int]]:
        """Cells that cover the segment from a to b.

        Cut into pieces no longer than a cell, each piece's bounding box spans at most 2 x 2
        cells. A long diagonal then costs about its length in cells, not its whole bounding box.
        """
        pieces = max(1, math.ceil(math.dist(a, b) / self._size))
        ends = [
            (a[0] + (b[0] - a[0]) * k / pieces, a[1] + (b[1] - a[1]) * k / pieces)
            for k in range(pieces + 1)
        ]
        cells: set[tuple[int, int]] = set()
        for p, q in itertools.pairwise(ends):
            x0, y0 = self._cell((min(p[0], q[0]), min(p[1], q[1])))
            x1, y1 = self._cell((max(p[0], q[0]), max(p[1], q[1])))
            cells.update(itertools.product(range(x0, x1 + 1), range(y0, y1 + 1)))
        return cells

    def _cell(self, p: Point) -> tuple[int, int]:
        return (
            math.floor((p[0] - self._origin[0]) / self._size),
            math.floor((p[1] - self._origin[1]) / self._size),
        )


def _ring(cx: int, cy: int, r: int, far: tuple[int, int]) -> Iterator[tuple[int, int]]:
    """The grid cells, from (0, 0) to far, exactly r steps (Chebyshev) from (cx, cy)."""
    fx, fy = far
    xs = range(max(cx - r, 0), min(cx + r, fx) + 1)
    for y in (cy - r, cy + r) if r else (cy,):
        if 0 <= y <= fy:
            yield from ((x, y) for x in xs)
    for x in (cx - r, cx + r) if r else ():
        if 0 <= x <= fx:
            yield from ((x, y) for y in range(max(cy - r + 1, 0), min(cy + r - 1, fy) + 1))


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
