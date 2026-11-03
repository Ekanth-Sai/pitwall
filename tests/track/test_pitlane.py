import pytest

from pitwall.track.geometry import Point
from pitwall.track.pitlane import pit_lane

# a 100 m square circuit, in decimetres; the "pit lane" runs 10 m below its bottom side.
# Runs here are a few points long, so most tests pass min_run=1
CIRCUIT: list[Point] = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]


def test_pit_lane_branches_off_and_rejoins() -> None:
    points: list[Point] = [(100, 0), (200, 0), (300, -100), (500, -100), (600, 0), (700, 0)]
    assert pit_lane(points, CIRCUIT, min_run=1) == [(200, 0), (300, -100), (500, -100), (600, 0)]


def test_ends_are_joined_onto_the_circuit() -> None:
    # the neighbours of the run are near the circuit, not on it; snap them onto it
    points: list[Point] = [(100, -30), (300, -100), (500, -30)]
    assert pit_lane(points, CIRCUIT, min_run=1) == [(100, 0), (300, -100), (500, 0)]


def test_longest_excursion_wins() -> None:
    # a one-sample wobble at x=100, then the real pit lane
    points: list[Point] = [(100, -100), (200, 0), (300, -100), (400, -100), (500, 0)]
    assert pit_lane(points, CIRCUIT, min_run=1) == [(200, 0), (300, -100), (400, -100), (500, 0)]


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        # already in the pit lane at the first sample: join from its own projection
        ([(300, -100), (400, -100), (500, 0)], [(300, 0), (300, -100), (400, -100), (500, 0)]),
        # still in the pit lane at the last sample
        ([(100, 0), (300, -100)], [(100, 0), (300, -100), (300, 0)]),
    ],
)
def test_run_at_either_end(points: list[Point], expected: list[Point]) -> None:
    assert pit_lane(points, CIRCUIT, min_run=1) == expected


def test_no_points_no_pit_lane() -> None:
    # returns before indexing the circuit, so even an empty circuit is fine
    assert pit_lane([], []) is None


def test_never_left_the_circuit() -> None:
    assert pit_lane([(100, 0), (200, 20), (300, 0)], CIRCUIT, min_run=1) is None


@pytest.mark.parametrize("offset", [0, -5])
def test_offset_must_be_positive(offset: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        pit_lane([(100, 0)], CIRCUIT, offset)


def test_short_excursion_is_not_a_pit_lane() -> None:
    # one stray sample 10 m off: a GPS spike or a wide moment, not a pit stop
    assert pit_lane([(100, 0), (200, 100), (300, 0)], CIRCUIT) is None


def test_min_run_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="min_run"):
        pit_lane([(100, 0)], CIRCUIT, min_run=0)
