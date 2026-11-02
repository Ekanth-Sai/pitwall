"""TrackOutline: the circuit and pit lane drawn under the cars, built once per track."""

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Self

from pitwall.errors import InsufficientDataError, SchemaError
from pitwall.ingest.openf1 import Lap, LocationSample
from pitwall.track.geometry import (
    CIRCUIT_POINTS,
    SMOOTH_WINDOW,
    Bounds,
    Point,
    principal_angle,
    resample,
    rotate,
    smooth_loop,
)
from pitwall.track.laps import lap_samples, representative_lap
from pitwall.track.pitlane import PIT_POINTS, pit_stop

FORMAT = 1  # bump when the JSON layout changes
MIN_LAP_SAMPLES = 100  # an ~80 s lap at ~4 Hz has 300+; far fewer means positions are missing


@dataclass(frozen=True)
class TrackOutline:
    """Circuit and pit lane in OpenF1 coordinates (decimetres, y up).

    rotation: degrees counter-clockwise about the origin that lay the track's long axis
    horizontal. The frontend rotates the track and the cars by the same angle.
    """

    circuit: tuple[Point, ...]
    pit_lane: tuple[Point, ...] | None
    rotation: float

    def __post_init__(self) -> None:
        if len(self.circuit) < 3:
            raise ValueError(f"circuit needs at least 3 points, got {len(self.circuit)}")
        if self.pit_lane is not None and len(self.pit_lane) < 2:
            raise ValueError(f"pit lane needs at least 2 points, got {len(self.pit_lane)}")

    @property
    def bounds(self) -> Bounds:
        """Bounding box after rotation: what the SVG viewBox must cover."""
        return Bounds.of(rotate(p, self.rotation) for p in [*self.circuit, *(self.pit_lane or ())])

    @classmethod
    def build(cls, laps: Sequence[Lap], samples: Sequence[LocationSample]) -> Self:
        """From one car's laps and location samples."""
        lap = representative_lap(laps)
        if lap is None:
            raise InsufficientDataError("no racing lap to draw the circuit from")
        raw: list[Point] = [(s.x, s.y) for s in lap_samples(lap, samples)]
        if len(raw) < MIN_LAP_SAMPLES:
            raise InsufficientDataError(
                f"lap {lap.number} has {len(raw)} position samples, need {MIN_LAP_SAMPLES}"
            )
        circuit = smooth_loop(resample(raw, CIRCUIT_POINTS, closed=True), SMOOTH_WINDOW)
        stop = pit_stop(laps, samples, circuit)
        pit = None if stop is None else resample(stop.lane, PIT_POINTS, closed=False)
        return cls(
            circuit=_rounded(circuit),
            pit_lane=None if pit is None else _rounded(pit),
            rotation=round(-principal_angle(circuit), 2),
        )

    def to_json(self) -> str:
        b = self.bounds
        data = {
            "format": FORMAT,
            "rotation": self.rotation,
            # for the frontend's viewBox; from_json recomputes it
            "bounds": [round(v, 1) for v in (b.min_x, b.min_y, b.max_x, b.max_y)],
            "circuit": self.circuit,
            "pit_lane": self.pit_lane,
        }
        return json.dumps(data, separators=(",", ":"))

    @classmethod
    def from_json(cls, text: str) -> Self:
        try:
            data = json.loads(text, parse_constant=_reject_constant)
        except ValueError as e:
            raise SchemaError(f"track outline is not valid JSON: {e}") from e
        if not isinstance(data, dict):
            raise SchemaError(f"track outline: expected an object, got {type(data).__name__}")
        version = data.get("format")
        if type(version) is not int or version != FORMAT:  # not true or 1.0: those pass == 1
            raise SchemaError(f"track outline format {version!r}, expected {FORMAT}")
        try:
            pit = data["pit_lane"]
            return cls(
                circuit=_points(data["circuit"]),
                pit_lane=None if pit is None else _points(pit),
                rotation=_number(data["rotation"]),
            )
        except (KeyError, TypeError, ValueError, OverflowError) as e:
            raise SchemaError(f"track outline: unexpected shape: {e!r}") from e


def _rounded(points: Sequence[Point]) -> tuple[Point, ...]:
    # 0.1 dm = 1 cm: far below the data's precision, and keeps the JSON short
    return tuple((round(x, 1), round(y, 1)) for x, y in points)


def _points(value: object) -> tuple[Point, ...]:
    if not isinstance(value, list):
        raise TypeError(f"expected a list of points, got {type(value).__name__}")
    return tuple(_point(item) for item in value)


def _point(item: object) -> Point:
    if not isinstance(item, list) or len(item) != 2:
        raise TypeError(f"expected a point [x, y], got {item!r}")
    return (_number(item[0]), _number(item[1]))


def _number(value: object) -> float:
    # bool is a subclass of int in Python, but true is not a coordinate
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"expected a number, got {type(value).__name__}")
    number = float(value)  # OverflowError for an int too big for a float
    # parse_constant stops NaN and Infinity, but 1e999 overflows to inf on its own
    if not math.isfinite(number):
        raise ValueError(f"expected a finite number, got {value!r}")
    return number


def _reject_constant(name: str) -> Any:
    # json.loads accepts NaN and Infinity by default; no coordinate can be either
    raise ValueError(f"{name} is not allowed")
