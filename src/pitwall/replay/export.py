"""One race as compact JSON for the browser replay: every car's position over time."""

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import accumulate, pairwise
from typing import Self

from pitwall.errors import InsufficientDataError
from pitwall.ingest.openf1 import Driver, Lap, LocationSample, Session
from pitwall.replay.colours import FALLBACK, ink_on
from pitwall.track.laps import last_lap_end
from pitwall.track.outline import TrackOutline

FORMAT = 1  # bump when the JSON layout changes
TAIL = timedelta(seconds=30)  # after the last lap ends, so the last cars cross the line


@dataclass(frozen=True)
class CarSamples:
    """One car's on-track positions: t in ms since the replay start, x and y in decimetres."""

    driver: Driver
    t: tuple[int, ...]
    x: tuple[int, ...]
    y: tuple[int, ...]

    def __post_init__(self) -> None:
        if not len(self.t) == len(self.x) == len(self.y):
            raise ValueError(f"t, x, y lengths differ: {len(self.t)}, {len(self.x)}, {len(self.y)}")
        if not self.t:
            raise ValueError(f"car {self.driver.number} has no samples")
        if self.t[0] < 0 or any(b <= a for a, b in pairwise(self.t)):
            raise ValueError(f"car {self.driver.number}: times must be >= 0 and increasing")


@dataclass(frozen=True)
class RaceReplay:
    session: Session
    start: datetime
    end: datetime
    track: TrackOutline
    cars: tuple[CarSamples, ...]

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"end {self.end} is not after start {self.start}")

    @staticmethod
    def window(laps: Iterable[Lap]) -> tuple[datetime, datetime]:
        """From the race start (the earliest lap 1 start) to TAIL after the last lap ends."""
        laps = list(laps)
        starts = [lap.start for lap in laps if lap.number == 1 and lap.start is not None]
        start = min(starts, default=None)
        end = last_lap_end(laps)
        if start is None or end is None:
            raise InsufficientDataError("no timed laps, so the race start or end is unknown")
        return start, end + TAIL

    @classmethod
    def build(
        cls,
        session: Session,
        drivers: Sequence[Driver],
        laps: Sequence[Lap],
        samples: Iterable[LocationSample],
        track: TrackOutline,
    ) -> Self:
        """Cars without an on-track sample in the window (example: a DNS) are left out."""
        start, end = cls.window(laps)
        by_car: defaultdict[int, list[LocationSample]] = defaultdict(list)
        for s in samples:
            if s.on_track and start <= s.time <= end:
                by_car[s.driver].append(s)
        cars = tuple(
            _car(d, by_car[d.number], start)
            for d in sorted(drivers, key=lambda d: d.number)
            if by_car[d.number]
        )
        if not cars:
            raise InsufficientDataError("no car has an on-track position in the race window")
        return cls(session=session, start=start, end=end, track=track, cars=cars)

    def to_json(self) -> str:
        data = {
            "format": FORMAT,
            "session": {
                "name": self.session.name,
                "location": self.session.location,
                "year": self.session.year,
            },
            "start": self.start.isoformat(),
            "duration_ms": _ms(self.end - self.start),
            "track": json.loads(self.track.to_json()),
            "cars": [_car_json(car) for car in self.cars],
        }
        return json.dumps(data, separators=(",", ":"))


def delta(values: Sequence[int]) -> list[int]:
    """The first value, then each value minus the one before it."""
    return [values[0], *(b - a for a, b in pairwise(values))] if values else []


def undelta(deltas: Sequence[int]) -> list[int]:
    """The inverse of delta: running sums."""
    return list(accumulate(deltas))


def _car(driver: Driver, samples: list[LocationSample], start: datetime) -> CarSamples:
    t: list[int] = []
    x: list[int] = []
    y: list[int] = []
    for s in sorted(samples, key=lambda s: s.time):
        ms = _ms(s.time - start)
        if t and ms == t[-1]:
            continue  # two samples in one millisecond: keep the first, times must increase
        t.append(ms)
        x.append(s.x)
        y.append(s.y)
    return CarSamples(driver=driver, t=tuple(t), x=tuple(x), y=tuple(y))


def _car_json(car: CarSamples) -> dict[str, object]:
    colour = car.driver.team_colour or FALLBACK
    return {
        "number": car.driver.number,
        "acronym": car.driver.acronym,
        "name": car.driver.full_name,
        "team": car.driver.team,
        "colour": colour,
        "ink": ink_on(colour),
        # deltas: consecutive samples are close, so the numbers stay short
        "t": delta(car.t),
        "x": delta(car.x),
        "y": delta(car.y),
    }


def _ms(d: timedelta) -> int:
    return round(d.total_seconds() * 1000)
