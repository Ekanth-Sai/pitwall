"""Profile raw OpenF1 rows: which fields an endpoint sends, how complete they are, how often."""

import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from typing import Self

from pitwall.errors import SchemaError
from pitwall.ingest.openf1 import Row

# Python type of a decoded JSON value -> the JSON name for it
_JSON_TYPES = {
    type(None): "null",
    bool: "bool",
    int: "int",
    float: "float",
    str: "string",
    list: "array",
    dict: "object",
}


@dataclass(frozen=True)
class FieldProfile:
    name: str
    types: Mapping[str, int]  # JSON type -> number of rows; a missing key counts as "absent"
    example: object  # the first non-null value, None if every row is null or absent


@dataclass(frozen=True)
class EndpointProfile:
    endpoint: str
    rows: int
    fields: tuple[FieldProfile, ...]  # sorted by name
    gaps: tuple[float, ...]  # seconds between consecutive rows of one driver (or the whole feed)

    @property
    def median_gap(self) -> float | None:
        return statistics.median(self.gaps) if self.gaps else None

    @classmethod
    def of(cls, endpoint: str, rows: Sequence[Row]) -> Self:
        names = sorted({name for row in rows for name in row})
        return cls(
            endpoint=endpoint,
            rows=len(rows),
            fields=tuple(_field(name, rows) for name in names),
            gaps=tuple(_gaps(endpoint, rows)),
        )


def json_type(value: object) -> str:
    try:
        return _JSON_TYPES[type(value)]
    except KeyError:
        raise ValueError(f"not a decoded JSON value: {type(value).__name__}") from None


def _field(name: str, rows: Sequence[Row]) -> FieldProfile:
    types = Counter(json_type(row[name]) if name in row else "absent" for row in rows)
    example = next((row[name] for row in rows if row.get(name) is not None), None)
    return FieldProfile(name, dict(types), example)


def _gaps(endpoint: str, rows: Sequence[Row]) -> Iterable[float]:
    """Per driver when every dated row has one, else across the whole feed.

    race_control mixes car messages with track-wide ones: its rate is the feed's, not a car's.
    """
    dated = [row for row in rows if row.get("date") is not None]
    per_driver = all(row.get("driver_number") is not None for row in dated)
    streams: defaultdict[str, list[datetime]] = defaultdict(list)
    for row in dated:
        # repr: any JSON value is a valid key, and 16 and "16" stay apart
        key = repr(row["driver_number"]) if per_driver else ""
        streams[key].append(_time(endpoint, row["date"]))
    for times in streams.values():
        times.sort()
        yield from ((b - a).total_seconds() for a, b in pairwise(times))


def _time(endpoint: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise SchemaError(f"{endpoint}: unreadable date: {value!r}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise SchemaError(f"{endpoint}: unreadable date: {value!r}") from e
