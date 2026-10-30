"""Pick the laps that draw the track: a typical racing lap, and pit in laps."""

import statistics
from collections.abc import Iterable, Sequence

from pitwall.ingest.openf1 import Lap, LocationSample

# Racing laps sit within 107% of the median; SC/VSC laps are far slower
SLOW_FACTOR = 1.07


def in_laps(laps: Sequence[Lap]) -> list[Lap]:
    """Laps that end in the pit lane. OpenF1 flags only the out-lap that follows"""
    _check_one_driver(laps)
    out = {lap.number for lap in laps if lap.pit_out}
    return [lap for lap in laps if lap.number + 1 in out]


def racing_laps(laps: Sequence[Lap], slow_factor: float = SLOW_FACTOR) -> list[Lap]:
    """Timed laps at racing speed: not lap 1, not pit in/out, not slow (SC/VSC)"""
    if slow_factor < 1:
        raise ValueError(f"slow_factor must be >= 1, got {slow_factor}")
    pit = {lap.number for lap in in_laps(laps)} | {lap.number for lap in laps if lap.pit_out}
    timed = _timed(lap for lap in laps if lap.number > 1 and lap.number not in pit)
    if not timed:
        return []
    limit = statistics.median(s for _, s in timed) * slow_factor
    return [lap for lap, s in timed if s <= limit]


def representative_lap(laps: Sequence[Lap]) -> Lap | None:
    """The racing lap closest to the median racing lap time: a typical line, no outliers."""
    timed = _timed(racing_laps(laps))
    if not timed:
        return None
    median = statistics.median(s for _, s in timed)
    return min(timed, key=lambda pair: abs(pair[1] - median))[0]


def lap_samples(lap: Lap, samples: Iterable[LocationSample]) -> list[LocationSample]:
    """The lap's driver's on-track samples in [start, end): consecutive laps never share one."""
    start, end = lap.start, lap.end
    if start is None or end is None:
        raise ValueError(f"lap {lap.number} has no timing")
    return [s for s in samples if s.driver == lap.driver and s.on_track and start <= s.time < end]


def _timed(laps: Iterable[Lap]) -> list[tuple[Lap, float]]:
    """(lap, seconds) for laps with full timing; the rest can't be placed in time."""
    return [
        (lap, lap.duration.total_seconds())
        for lap in laps
        if lap.start is not None and lap.duration is not None
    ]


def _check_one_driver(laps: Sequence[Lap]) -> None:
    # lap numbers are per driver, so mixing drivers would pair up the wrong laps
    if len({lap.driver for lap in laps}) > 1:
        raise ValueError("expected the laps of a single driver")
