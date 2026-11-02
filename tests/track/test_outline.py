"""
It uses a synthetic race: an ellipse 4 km by 1 km, tilted 30°, with a pit stop where the
car runs 2% wide.
"""

import json
import math
from datetime import UTC, datetime, timedelta

import pytest

from pitwall.errors import InsufficientDataError, SchemaError
from pitwall.ingest.openf1 import Lap, LocationSample
from pitwall.track.geometry import Point, nearest_on_loop, rotate
from pitwall.track.outline import TrackOutline

T0 = datetime(2024, 9, 1, 13, 0, tzinfo=UTC)
LAP = 90.0  # seconds
TILT = 30.0  # degrees: the synthetic track's long axis


def on_track(t: float) -> Point:
    """An ellipse 4 km by 1 km, tilted by TILT, driven once per LAP seconds."""
    a = 2 * math.pi * (t % LAP) / LAP
    return rotate((20_000 * math.cos(a), 5_000 * math.sin(a)), TILT)


def race(
    n_laps: int = 6, pit_lap: int | None = 3, hz: float = 2, wide: float = 1.02
) -> tuple[list[Lap], list[LocationSample]]:
    """Back-to-back laps. With a pit stop, the car runs wide 20 s either side of pit_lap's end."""
    laps = [
        Lap(
            16,
            n,
            T0 + timedelta(seconds=(n - 1) * LAP),
            timedelta(seconds=LAP),
            pit_out=n == (pit_lap or 0) + 1,
        )
        for n in range(1, n_laps + 1)
    ]
    samples = []
    for i in range(int(n_laps * LAP * hz)):
        t = i / hz
        x, y = on_track(t)
        if pit_lap is not None and abs(t - pit_lap * LAP) < 20:
            x, y = x * wide, y * wide  # 2% outward: 10-40 m off the ellipse
        samples.append(LocationSample(T0 + timedelta(seconds=t), 16, round(x), round(y), 0))
    return laps, samples


@pytest.fixture(scope="module")
def outline() -> TrackOutline:
    return TrackOutline.build(*race())


# build


def test_long_axis_is_laid_horizontal(outline: TrackOutline) -> None:
    assert outline.rotation == pytest.approx(-TILT, abs=0.5)
    assert outline.bounds.width > 3 * outline.bounds.height


def test_circuit_follows_the_track(outline: TrackOutline) -> None:
    assert len(outline.circuit) == 500
    track = [on_track(t / 10) for t in range(int(LAP * 10))]
    # within 1 m: smoothing cuts the ellipse's tight ends a little
    assert max(math.dist(p, nearest_on_loop(p, track)) for p in outline.circuit[::10]) < 10


def test_pit_lane_found_off_the_circuit(outline: TrackOutline) -> None:
    assert outline.pit_lane is not None
    assert len(outline.pit_lane) == 100
    middle = outline.pit_lane[50]
    assert math.dist(middle, nearest_on_loop(middle, outline.circuit)) > 50


def test_no_pit_stop_no_pit_lane() -> None:
    assert TrackOutline.build(*race(pit_lap=None)).pit_lane is None


def test_stop_that_never_leaves_the_circuit() -> None:
    assert TrackOutline.build(*race(wide=1.0)).pit_lane is None


def test_untimed_stop_skipped() -> None:
    laps, samples = race()
    laps[3] = Lap(16, 4, laps[3].start, None, pit_out=True)  # out-lap without a duration
    assert TrackOutline.build(laps, samples).pit_lane is None


def test_no_racing_lap() -> None:
    with pytest.raises(InsufficientDataError, match="no racing lap"):
        TrackOutline.build(*race(n_laps=1, pit_lap=None))


def test_too_few_samples() -> None:
    with pytest.raises(InsufficientDataError, match="samples"):
        TrackOutline.build(*race(pit_lap=None, hz=1))  # 90 per lap


@pytest.mark.parametrize(
    ("circuit", "pit_lane", "message"),
    [
        (((0, 0), (1, 0)), None, "circuit"),
        (((0, 0), (1, 0), (1, 1)), ((0, 0),), "pit lane"),
    ],
)
def test_invariants(
    circuit: tuple[Point, ...], pit_lane: tuple[Point, ...] | None, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        TrackOutline(circuit, pit_lane, 0.0)


# JSON


def test_json_round_trip(outline: TrackOutline) -> None:
    assert TrackOutline.from_json(outline.to_json()) == outline


def test_json_carries_bounds_for_the_frontend(outline: TrackOutline) -> None:
    data = json.loads(outline.to_json())
    b = outline.bounds
    assert data["format"] == 1
    assert data["bounds"] == pytest.approx([b.min_x, b.min_y, b.max_x, b.max_y], abs=0.05)


def test_json_without_pit_lane() -> None:
    track = TrackOutline(((0, 0), (10, 0), (10, 10)), None, 0.0)
    assert TrackOutline.from_json(track.to_json()) == track


GOOD = {"format": 1, "rotation": 0, "circuit": [[0, 0], [10, 0], [10, 10]], "pit_lane": None}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{not json", "not valid JSON"),
        (json.dumps({**GOOD, "rotation": math.nan}), "NaN is not allowed"),
        ("[]", "expected an object"),
        (json.dumps({**GOOD, "format": 2}), "format 2"),
        (json.dumps({**GOOD, "format": True}), "format True"),
        (json.dumps({**GOOD, "format": 1.0}), "format 1.0"),
        (json.dumps({k: v for k, v in GOOD.items() if k != "rotation"}), "rotation"),
        (json.dumps({**GOOD, "circuit": [[0, 0], [10, 0]]}), "at least 3"),
        (json.dumps({**GOOD, "circuit": [[0, 0, 0], [10, 0], [10, 10]]}), "point"),
        (json.dumps({**GOOD, "circuit": [[True, 0], [10, 0], [10, 10]]}), "number"),
        (json.dumps(GOOD).replace('"rotation": 0', '"rotation": 1e999'), "finite"),
        (json.dumps({**GOOD, "rotation": 10**400}), "too large"),
        (json.dumps({**GOOD, "pit_lane": "pit"}), "list of points"),
    ],
)
def test_bad_json_rejected(text: str, message: str) -> None:
    with pytest.raises(SchemaError, match=message):
        TrackOutline.from_json(text)
