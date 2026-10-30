from collections.abc import Collection
from datetime import UTC, datetime, timedelta

import pytest

from pitwall.ingest.openf1 import Lap, LocationSample
from pitwall.track.laps import in_laps, lap_samples, racing_laps, representative_lap

T0 = datetime(2024, 9, 1, 13, 0, tzinfo=UTC)


def make_laps(
    seconds: list[float | None], pit_out: Collection[int] = (), driver: int = 16
) -> list[Lap]:
    """Back-to-back laps numbered from 1; None means the lap has no timing."""
    laps: list[Lap] = []
    t = T0
    for number, s in enumerate(seconds, start=1):
        duration = None if s is None else timedelta(seconds=s)
        laps.append(Lap(driver, number, t, duration, pit_out=number in pit_out))
        t += timedelta(seconds=s or 90)
    return laps


def numbers(laps: list[Lap]) -> list[int]:
    return [lap.number for lap in laps]


def sample(t: datetime, driver: int = 16, x: int = 1, y: int = 1) -> LocationSample:
    return LocationSample(time=t, driver=driver, x=x, y=y, z=0)


# in_laps


def test_in_lap_is_the_lap_before_an_out_lap() -> None:
    laps = make_laps([88, 85, 86, 105, 85], pit_out={5})
    assert numbers(in_laps(laps)) == [4]


def test_no_pit_stop_no_in_laps() -> None:
    assert in_laps(make_laps([88, 85, 86])) == []


def test_mixed_drivers_rejected() -> None:
    laps = make_laps([85, 85]) + make_laps([85], driver=1)
    with pytest.raises(ValueError, match="single driver"):
        in_laps(laps)


# racing laps


def test_racing_laps_skip_lap1_pit_laps_and_untimed() -> None:
    # 1: start, 4: in-lap, 5: out-lap, 6: untimed
    laps = make_laps([88, 85, 86, 90, 105, None, 85.5], pit_out={5})
    assert numbers(racing_laps(laps)) == [2, 3, 7]


def test_slow_laps_excluded() -> None:
    # laps 4-5 behind the safety car, about 40% slower than the median
    laps = make_laps([88, 85, 86, 120, 118, 85.5, 86.2])
    assert numbers(racing_laps(laps)) == [2, 3, 6, 7]


def test_no_racing_laps() -> None:
    assert racing_laps(make_laps([88])) == []


def test_slow_factor_below_one_rejected() -> None:
    with pytest.raises(ValueError, match="slow_factor"):
        racing_laps(make_laps([88, 85]), slow_factor=0.9)


# representative lap


def test_representative_is_closest_to_median() -> None:
    # racing laps 2-6 sorted: 84, 85, 85.8, 86, 87.5 -> median 85.8 is lap 6
    laps = make_laps([88, 86, 84, 85, 87.5, 85.8])
    chosen = representative_lap(laps)
    assert chosen is not None
    assert chosen.number == 6


def test_no_representative_without_racing_laps() -> None:
    assert representative_lap(make_laps([88])) is None


# lap_samples


def test_lap_samples_half_open_on_track_same_driver() -> None:
    lap = make_laps([85])[0]
    end = T0 + timedelta(seconds=85)
    samples = [
        sample(T0 - timedelta(seconds=1)),  # before the lap
        sample(T0),  # start: included
        sample(T0 + timedelta(seconds=40)),
        sample(T0 + timedelta(seconds=41), x=0, y=0),  # no position
        sample(T0 + timedelta(seconds=42), driver=1),  # another car
        sample(end),  # end: belongs to the next lap
    ]
    assert [s.time for s in lap_samples(lap, samples)] == [T0, T0 + timedelta(seconds=40)]


def test_untimed_lap_cannot_be_sliced() -> None:
    lap = make_laps([None])[0]
    with pytest.raises(ValueError, match="no timing"):
        lap_samples(lap, [])
