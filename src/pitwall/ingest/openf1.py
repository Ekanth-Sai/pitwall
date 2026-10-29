"""OpenF1 client: validated queries and typed results from api.openf1.org"""

import json
import logging
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Self

from pitwall.errors import InvalidQueryError, SchemaError, SourceError
from pitwall.ingest.transport import Params, Transport

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openf1.org/v1/"
DEFAULT_CHUNK = timedelta(minutes=10)
_PAD = timedelta(seconds=1)

Row = dict[str, Any]

# A filter key is a field name, optionally followed by one comparison operator
_FILTER_KEY = re.compile(r"(?P<field>[a-z_]+)(?P<op>[<>])?")

# Filterable fields per endpoint. OpenF1 answers an unknown field with the same 404
# as "no results", so typos must be rejected before the request is sent.
FIELDS: dict[str, frozenset[str]] = {
    "sessions": frozenset(
        {
            "session_key",
            "meeting_key",
            "year",
            "circuit_short_name",
            "country_code",
            "country_key",
            "country_name",
            "location",
            "session_name",
            "session_type",
            "date_start",
            "date_end",
        }
    ),
    "drivers": frozenset(
        {
            "session_key",
            "meeting_key",
            "driver_number",
            "name_acronym",
            "full_name",
            "first_name",
            "last_name",
            "broadcast_name",
            "country_code",
            "team_name",
            "team_colour",
        }
    ),
    "location": frozenset({"session_key", "meeting_key", "driver_number", "date", "x", "y", "z"}),
}


@dataclass(frozen=True)
class Session:
    key: int
    name: str
    location: str
    year: int
    start: datetime
    end: datetime  # scheduled end, not the actual finish

    @classmethod
    def from_row(cls, row: Row) -> Self:
        return cls(
            key=int(row["session_key"]),
            name=_text(row["session_name"]),
            location=_text(row["location"]),
            year=int(row["year"]),
            start=datetime.fromisoformat(row["date_start"]),
            end=datetime.fromisoformat(row["date_end"]),
        )


@dataclass(frozen=True)
class Driver:
    number: int
    acronym: str
    full_name: str
    team: str
    team_colour: str | None  # hex without '#'; OpenF1 sometimes sends null

    @classmethod
    def from_row(cls, row: Row) -> Self:
        return cls(
            number=int(row["driver_number"]),
            acronym=_text(row["name_acronym"]),
            full_name=_text(row["full_name"]),
            team=_text(row["team_name"]),
            team_colour=row["team_colour"] or None,
        )


@dataclass(frozen=True)
class LocationSample:
    time: datetime
    driver: int
    x: int
    y: int
    z: int

    @classmethod
    def from_row(cls, row: Row) -> Self:
        return cls(
            time=datetime.fromisoformat(row["date"]),
            driver=int(row["driver_number"]),
            x=int(row["x"]),
            y=int(row["y"]),
            z=int(row["z"]),
        )


def _text(value: object) -> str:
    """Strict str(): JSON null must not become the strinf 'None'."""
    if not isinstance(value, str):
        raise TypeError(f"expected a string, got {type(value).__name__}")
    return value


def _parse[T](rows: list[Row], factory: Callable[[Row], T], endpoint: str) -> list[T]:
    try:
        return [factory(row) for row in rows]
    except (KeyError, TypeError, ValueError) as e:
        raise SchemaError(f"{endpoint}: unexpected row shape: {e!r}") from e


def _fmt(t: datetime) -> str:
    if t.tzinfo is None:
        raise ValueError(f"naive datetime {t!r}; pass a timezone-aware (UTC) datetime")
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")


class OpenF1Client:
    def __init__(self, transport: Transport, chunk: timedelta = DEFAULT_CHUNK) -> None:
        if chunk <= timedelta(0):
            raise ValueError(f"chunk must be positive, got {chunk}")
        self._transport = transport
        self._chunk = chunk

    def query(self, endpoint: str, params: Params) -> list[Row]:
        """Validated raw query. 404 means 'no rows' once filters are known-good."""
        self._validate(endpoint, params)
        response = self._transport.get(endpoint, params)
        if response.status == 404:
            return []
        if response.status != 200:
            raise SourceError(f"GET {endpoint} returned HTTP {response.status}")
        try:
            rows = json.loads(response.body)
        except json.JSONDecodeError as e:
            raise SchemaError(f"{endpoint}: response is not valid JSON") from e
        if not isinstance(rows, list):
            raise SchemaError(f"{endpoint}: expected a JSON list, got {type(rows).__name__}")
        return rows

    def sessions(self, year: int, circuit: str, name: str) -> list[Session]:
        params: Params = {"year": year, "circuit_short_name": circuit, "session_name": name}
        return _parse(self.query("sessions", params), Session.from_row, "sessions")

    def drivers(self, session_key: int) -> list[Driver]:
        rows = self.query("drivers", {"session_key": session_key})
        return _parse(rows, Driver.from_row, "drivers")

    def locations(
        self, session_key: int, start: datetime, end: datetime, driver: int | None = None
    ) -> list[LocationSample]:
        """Locations in [start, end], fetched in chunks; boundary duplicates removed."""
        if end < start:
            raise ValueError(f"end {end} is before start {start}")
        unique: dict[tuple[datetime, int], LocationSample] = {}
        for lo, hi in self._windows(start, end):
            # pad by 1 s: _fmt drops sub-secods, and we must not depend on whether the
            # server treats date>/date< as strict or inclusive. Trimmed + deduped below.
            params: Params = {
                "session_key": session_key,
                "date>": _fmt(lo - _PAD),
                "date<": _fmt(hi + _PAD),
            }
            if driver is not None:
                params["driver_number"] = driver
            samples = _parse(self.query("location", params), LocationSample.from_row, "location")
            logger.debug("location %s..%s: %d rows", lo, hi, len(samples))
            for s in samples:
                if start <= s.time <= end:
                    unique[(s.time, s.driver)] = s
        return sorted(unique.values(), key=lambda s: (s.time, s.driver))

    def _windows(self, start: datetime, end: datetime) -> Iterator[tuple[datetime, datetime]]:
        t = start
        while t < end:
            yield t, min(t + self._chunk, end)
            t += self._chunk

    @staticmethod
    def _validate(endpoint: str, params: Params) -> None:
        allowed = FIELDS.get(endpoint)
        if allowed is None:
            raise InvalidQueryError(f"unknown endpoint {endpoint}")
        for key in params:
            m = _FILTER_KEY.fullmatch(key)
            if m is None or m["field"] not in allowed:
                raise InvalidQueryError(f"{endpoint}: invalid filter {key!r}")
