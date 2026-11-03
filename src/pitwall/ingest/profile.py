"""Profile raw OpenF1 rows: which fields an endpoint sends, how complete they are, how often."""

import statistics
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby, pairwise
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

    @property
    def nulls(self) -> int:
        return self.types.get("null", 0) + self.types.get("absent", 0)


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
        try:
            gaps = tuple(_gaps(rows))
        except (TypeError, ValueError) as e:
            raise SchemaError(f"{endpoint}: unreadable date: {e!r}") from e
        return cls(
            endpoint=endpoint,
            rows=len(rows),
            fields=tuple(_field(name, rows) for name in names),
            gaps=gaps,
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


def _gaps(rows: Sequence[Row]) -> Iterable[float]:
    """Per driver when rows carry one, else across the whole feed (weather, race control)."""
    timed = [
        (row.get("driver_number"), datetime.fromisoformat(row["date"]))
        for row in rows
        if "date" in row
    ]
    timed.sort(key=lambda pair: (pair[0] is None, pair[0] or 0, pair[1]))
    for _, group in groupby(timed, key=lambda pair: pair[0]):
        times = [t for _, t in group]
        yield from ((b - a).total_seconds() for a, b in pairwise(times))
