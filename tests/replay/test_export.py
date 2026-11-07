import json
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pitwall.errors import InsufficientDataError
from pitwall.ingest.openf1 import Driver, Lap, LocationSample, Session
from pitwall.replay.export import FORMAT, TAIL, CarSamples, RaceReplay, delta, undelta
from pitwall.track.outline import TrackOutline

T0 = datetime(2024, 9, 1, 13, 3, tzinfo=UTC)
SESSION = Session(9590, "Race", "Monza", 2024, T0, T0 + timedelta(hours=2))
TRACK = TrackOutline(circuit=((0.0, 0.0), (100.0, 0.0), (0.0, 50.0)), pit_lane=None, rotation=0.0)
LEC = Driver(16, "LEC", "Charles LECLERC", "Ferrari", "E80020")
PIA = Driver(81, "PIA", "Oscar PIASTRI", "McLaren", "FF8000")
NOCOLOUR = Driver(99, "XXX", "No COLOUR", "Mystery", None)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def lap(driver: int, number: int, start: float | None, seconds: float | None = 80.0) -> Lap:
    return Lap(
        driver,
        number,
        None if start is None else at(start),
        None if seconds is None else timedelta(seconds=seconds),
        pit_out=False,
    )


def sample(driver: int, seconds: float, x: int = 10, y: int = 20) -> LocationSample:
    return LocationSample(at(seconds), driver, x, y, 0)


# two laps each; LEC starts 0.5 s before PIA, PIA finishes last at 160.5 s
LAPS = [lap(16, 1, 0.0), lap(16, 2, 80.0), lap(81, 1, 0.5), lap(81, 2, 80.5)]


def build(samples: list[LocationSample], drivers: tuple[Driver, ...] = (LEC, PIA)) -> RaceReplay:
    return RaceReplay.build(SESSION, drivers, LAPS, samples, TRACK)


# window


def test_window_runs_from_the_first_lap_one_start_to_tail_after_the_last_lap() -> None:
    assert RaceReplay.window(LAPS) == (at(0.0), at(160.5) + TAIL)


def test_window_ignores_laps_without_timing() -> None:
    laps = [*LAPS, lap(44, 1, None), lap(44, 2, 300.0, None)]
    assert RaceReplay.window(laps) == (at(0.0), at(160.5) + TAIL)


@pytest.mark.parametrize(
    "laps",
    [[], [lap(16, 1, None), lap(16, 2, None)], [lap(16, 2, 80.0)]],
    ids=["no laps", "no timing", "no lap 1"],
)
def test_window_needs_a_timed_lap_one_and_a_lap_end(laps: list[Lap]) -> None:
    with pytest.raises(InsufficientDataError, match="race start or end is unknown"):
        RaceReplay.window(laps)


# build


def test_build_keeps_each_cars_samples_in_time_order() -> None:
    replay = build([sample(16, 2.0, 3, 4), sample(81, 1.0), sample(16, 1.0, 1, 2)])
    lec, pia = replay.cars
    assert lec.driver == LEC
    assert (lec.t, lec.x, lec.y) == ((1000, 2000), (1, 3), (2, 4))
    assert pia.t == (1000,)


def test_build_drops_off_track_and_out_of_window_samples() -> None:
    off_track = LocationSample(at(5.0), 16, 0, 0, 0)
    early, late = sample(16, -1.0), sample(16, 160.5 + TAIL.total_seconds() + 0.1)
    replay = build([early, off_track, sample(16, 5.0), late, sample(81, 6.0)])
    assert replay.cars[0].t == (5000,)


def test_build_leaves_out_cars_without_samples_and_unknown_cars() -> None:
    replay = build([sample(81, 1.0), sample(44, 1.0)])  # 16 has none; 44 isn't a driver
    assert [car.driver.number for car in replay.cars] == [81]


def test_build_keeps_one_sample_per_millisecond() -> None:
    replay = build([sample(16, 1.0, x=1), sample(16, 1.0002, x=2), sample(16, 1.002, x=3)])
    assert replay.cars[0].t == (1000, 1002)
    assert replay.cars[0].x == (1, 3)


def test_build_with_no_samples_at_all_is_insufficient() -> None:
    with pytest.raises(InsufficientDataError, match="no car has an on-track position"):
        build([LocationSample(at(5.0), 16, 0, 0, 0)])


# validation


@pytest.mark.parametrize(
    ("t", "x", "y", "message"),
    [
        ((0, 1), (0,), (0, 0), "lengths differ"),
        ((), (), (), "has no samples"),
        ((-1, 5), (0, 0), (0, 0), "must be >= 0 and increasing"),
        ((5, 5), (0, 0), (0, 0), "must be >= 0 and increasing"),
        ((5, 4), (0, 0), (0, 0), "must be >= 0 and increasing"),
    ],
)
def test_car_samples_reject_bad_arrays(
    t: tuple[int, ...], x: tuple[int, ...], y: tuple[int, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        CarSamples(LEC, t, x, y)


def test_replay_must_end_after_it_starts() -> None:
    car = CarSamples(LEC, (0,), (0,), (0,))
    with pytest.raises(ValueError, match="is not after start"):
        RaceReplay(SESSION, at(10.0), at(10.0), TRACK, (car,))


# JSON


def test_json_has_the_session_window_and_track() -> None:
    data = json.loads(build([sample(16, 1.0)]).to_json())
    assert data["format"] == FORMAT
    assert data["session"] == {"name": "Race", "location": "Monza", "year": 2024}
    assert data["start"] == "2024-09-01T13:03:00+00:00"
    assert data["duration_ms"] == 190_500  # 160.5 s of laps + 30 s tail
    assert data["track"] == json.loads(TRACK.to_json())


def test_json_cars_decode_back_to_the_samples() -> None:
    samples = [sample(16, s, x=100 + i * 7, y=-50 - i * 3) for i, s in enumerate([1.0, 1.25, 1.5])]
    replay = build(samples)
    (car,) = json.loads(replay.to_json())["cars"]
    assert {k: car[k] for k in ("number", "acronym", "name", "team", "colour", "ink")} == {
        "number": 16,
        "acronym": "LEC",
        "name": "Charles LECLERC",
        "team": "Ferrari",
        "colour": "E80020",
        "ink": "white",
    }
    lec = replay.cars[0]
    assert car["t"] == [1000, 250, 250]
    assert (undelta(car["t"]), undelta(car["x"]), undelta(car["y"])) == (
        list(lec.t),
        list(lec.x),
        list(lec.y),
    )


def test_json_gives_a_missing_team_colour_grey_with_readable_ink() -> None:
    (car,) = json.loads(build([sample(99, 1.0)], (NOCOLOUR,)).to_json())["cars"]
    assert (car["colour"], car["ink"]) == ("808080", "black")


def test_json_has_no_padding_after_separators() -> None:
    text = build([sample(16, 1.0)]).to_json()
    assert ", " not in text
    assert ": " not in text


# delta coding


@given(st.lists(st.integers(min_value=-(10**9), max_value=10**9)))
def test_undelta_inverts_delta(values: list[int]) -> None:
    assert undelta(delta(values)) == values


def test_delta_of_known_values() -> None:
    assert delta([5, 7, 4]) == [5, 2, -3]
    assert delta([]) == []
