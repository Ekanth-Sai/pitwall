import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pitwall.track.geometry import Point, path_length, resample, smooth_loop

# OpenF1 positions are integers in decimetres, a few km across
coord = st.integers(-20_000, 20_000).map(float)
point = st.tuples(coord, coord)
paths = st.lists(point, min_size=3, max_size=40, unique=True)
SQUARE: list[Point] = [(0, 0), (10, 0), (10, 10), (0, 10)]


def close(a: Point, b: Point) -> bool:
    return math.dist(a, b) < 1e-6


# examples


def test_square_resampled_to_corners_and_midpoints() -> None:
    assert resample(SQUARE, 8, closed=True) == [
        (0, 0),
        (5, 0),
        (10, 0),
        (10, 5),
        (10, 10),
        (5, 10),
        (0, 10),
        (0, 5),
    ]


def test_open_line_evenly_spaced_with_both_ends() -> None:
    assert resample([(0, 0), (1, 0), (10, 0)], 5, closed=False) == [
        (0, 0),
        (2.5, 0),
        (5, 0),
        (7.5, 0),
        (10, 0),
    ]


def test_repeated_points_are_skipped() -> None:
    assert resample([(0, 0), (0, 0), (4, 0)], 3, closed=False) == [(0, 0), (2, 0), (4, 0)]


def test_smooth_wraps_around_the_start() -> None:
    # point 0's neighbours are point 3 (before it, across the line) and point 1
    assert smooth_loop(SQUARE, 3)[0] == pytest.approx((10 / 3, 10 / 3))


def test_path_length() -> None:
    assert path_length(SQUARE) == 30  # open: 3 sides


# errors


@pytest.mark.parametrize(
    ("points", "n", "closed", "message"),
    [
        (SQUARE, 1, True, "at least 2"),
        ([(0, 0), (1, 1)], 5, True, "too few points"),
        ([(0, 0)], 5, False, "too few points"),
        ([(3, 3), (3, 3), (3, 3)], 5, True, "zero length"),
    ],
)
def test_resample_rejects_bad_input(
    points: list[Point], n: int, closed: bool, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        resample(points, n, closed=closed)


@pytest.mark.parametrize(("window", "message"), [(0, "odd"), (2, "odd"), (5, "longer")])
def test_smooth_rejects_bad_window(window: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        smooth_loop(SQUARE, window)


# properties


@given(paths, st.integers(2, 200), st.booleans())
def test_resample_count_and_start(points: list[Point], n: int, closed: bool) -> None:
    out = resample(points, n, closed=closed)
    assert len(out) == n
    assert close(out[0], points[0])


@given(paths, st.integers(2, 200))
def test_open_resample_keeps_the_end(points: list[Point], n: int) -> None:
    assert close(resample(points, n, closed=False)[-1], points[-1])


@given(paths, st.integers(3, 200))
def test_resampling_never_lengthens_a_loop(points: list[Point], n: int) -> None:
    # every new point lies on the old path, so the new path cuts corners or matches it
    out = resample(points, n, closed=True)
    assert path_length([*out, out[0]]) <= path_length([*points, points[0]]) + 1e-6


@given(paths, st.integers(2, 100), point)
def test_resample_commutes_with_translation(points: list[Point], n: int, shift: Point) -> None:
    dx, dy = shift
    moved = [(x + dx, y + dy) for x, y in points]
    expected = [(x + dx, y + dy) for x, y in resample(points, n, closed=True)]
    assert all(close(a, b) for a, b in zip(resample(moved, n, closed=True), expected, strict=True))


@given(paths, st.sampled_from([1, 3]))
def test_smoothing_keeps_count_and_centroid(points: list[Point], window: int) -> None:
    out = smooth_loop(points, window)
    assert len(out) == len(points)
    mean = (sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points))
    new_mean = (sum(x for x, _ in out) / len(out), sum(y for _, y in out) / len(out))
    assert math.dist(mean, new_mean) < 1e-6


@given(paths)
def test_window_one_is_identity(points: list[Point]) -> None:
    assert smooth_loop(points, 1) == points
