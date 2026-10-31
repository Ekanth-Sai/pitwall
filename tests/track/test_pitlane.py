import pytest

from pitwall.track.geometry import Point
from pitwall.track.pitlane import pit_lane

# a 100 m square circuit, in decimetres; the "pit lane" runs 10 m below its bottom slide
CIRCUIT: list[Point] = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]


def test_pit_lane_branches_off_and_rejoins() -> None:
    points: list[Point] = [(100, 0), (200, 0), (300, -100), (500, -100), (600, 0), (700, 0)]
    assert pit_lane(points, CIRCUIT) == [(200, 0), (300, -100), (500, -100), (600, 0)]


def test_ends_are_joined_onto_the_circuit() -> None:
    # the neighbours of the run are near the circuit, not on it; snap them onto it
    points: list[Point] = [(100, -30), (300, -100), (500, -30)]
    assert pit_lane(points, CIRCUIT) == [(100, 0), (300, -100), (500, 0)]


def test_longest_excursion_wins() -> None:
    # a one-sample wobble at x=100, then the real pit lane
    points: list[Point] = [(100, -100), (200, 0), (300, -100), (400, -100), (500, 0)]
    assert pit_lane(points, CIRCUIT) == [(200, 0), (300, -100), (400, -100), (500, 0)]


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
    assert pit_lane(points, CIRCUIT) == expected


def test_never_left_the_circuit() -> None:
    assert pit_lane([(100, 0), (200, 20), (300, 0)], CIRCUIT) is None


@pytest.mark.parametrize("offset", [0, -5])
def test_offset_must_be_positive(offset: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        pit_lane([(100, 0)], CIRCUIT, offset)
