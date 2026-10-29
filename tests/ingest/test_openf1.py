import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from pitwall.errors import InvalidQueryError, SchemaError, SourceError
from pitwall.ingest.openf1 import Driver, LocationSample, OpenF1Client, Session
from pitwall.ingest.transport import Params, Response

Row = dict[str, Any]
T0 = datetime(2024, 9, 1, 13, 0, tzinfo=UTC)
NOT_FOUND = Response(404, b'{"detail": "No results found."}')


def ok(rows: list[Row]) -> Response:
    return Response(200, json.dumps(rows).encode())


def loc(date: str, driver: int = 16, x: int = 1, y: int = 2) -> Row:
    return {"date": date, "driver_number": driver, "x": x, "y": y, "z": 0}


class FakeTransport:
    def __init__(self, handler: Callable[[str, Params], Response]) -> None:
        self.handler = handler
        self.calls: list[tuple[str, Params]] = []

    def get(self, endpoint: str, params: Params) -> Response:
        self.calls.append((endpoint, dict(params)))
        return self.handler(endpoint, params)


def client_returning(response: Response) -> tuple[OpenF1Client, FakeTransport]:
    fake = FakeTransport(lambda _e, _p: response)
    return OpenF1Client(fake), fake


# validation


@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        ("location", {"drive_number": 16}),  # the real typo comes from Phase 0
        ("location", {"dat>": "2024-09-01T13:00:00"}),
        ("teleport", {"session_key": 1}),
        ("location", {"date<>": "2024-09-01T13:00:00"}),
        ("location", {"session_key>>": 1}),
        ("location", {"date>=": "2024-09-01T13:00:00"}),
    ],
)
def test_invalid_query_rejected_before_request(endpoint: str, params: Params) -> None:
    client, fake = client_returning(ok([]))
    with pytest.raises(InvalidQueryError):
        client.query(endpoint, params)
    assert fake.calls == []


def test_operator_suffixes_are_allowed() -> None:
    client, fake = client_returning(ok([]))
    client.query("location", {"date>": "a", "date<": "b"})
    assert len(fake.calls) == 1


# response handling


def test_404_means_no_rows() -> None:
    client, _ = client_returning(NOT_FOUND)
    assert client.query("location", {"session_key": 1}) == []


@pytest.mark.parametrize("status", [401, 429, 500])
def test_error_status_raises_source_error(status: int) -> None:
    client, _ = client_returning(Response(status, b""))
    with pytest.raises(SourceError, match=f"HTTP {status}"):
        client.query("location", {"session_key": 1})


def test_invalid_json_raises_schema_error() -> None:
    client, _ = client_returning(Response(200, b"not json"))
    with pytest.raises(SchemaError, match="not valid JSON") as exc_info:
        client.query("location", {})
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


def test_non_list_json_raises_schema_error() -> None:
    client, _ = client_returning(Response(200, b'{"detail": "x"}'))
    with pytest.raises(SchemaError, match="expected a JSON list"):
        client.query("location", {})


# typed endpoints


def test_session_parsed() -> None:
    row = {
        "session_key": 9590,
        "session_name": "Race",
        "location": "Monza",
        "year": 2024,
        "date_start": "2024-09-01T13:00:00+00:00",
        "date_end": "2024-09-01T15:00:00+00:00",
    }
    client, fake = client_returning(ok([row]))

    assert client.sessions(2024, "Monza", "Race") == [
        Session(9590, "Race", "Monza", 2024, T0, T0 + timedelta(hours=2))
    ]
    assert fake.calls[0][1]["circuit_short_name"] == "Monza"


def test_drivers_parsed_with_null_colours() -> None:
    row = {
        "driver_number": 16,
        "name_acronym": "LEC",
        "full_name": "Charles LECLERC",
        "team_name": "Ferrari",
        "team_colour": None,
    }
    client, _ = client_returning(ok([row]))
    assert client.drivers(9590) == [Driver(16, "LEC", "Charles LECLERC", "Ferrari", None)]


def test_bad_row_shape_raises_schema_error() -> None:
    client, _ = client_returning(ok([{"driver_number": 16}]))  # missing fields
    with pytest.raises(SchemaError, match="drivers: unexpected row shape") as exc_info:
        client.drivers(9590)
    assert isinstance(exc_info.value.__cause__, KeyError)


@pytest.mark.parametrize("field", ["name_acronym", "full_name", "team_name"])
def test_null_text_field_raises_schema_error(field: str) -> None:
    row: Row = {
        "driver_number": 16,
        "name_acronym": "LEC",
        "full_name": "Charles LECLERC",
        "team_name": "Ferrari",
        "team_colour": None,
    }
    row[field] = None
    client, _ = client_returning(ok([row]))
    with pytest.raises(SchemaError, match="expected a string"):
        client.drivers(9590)


# chunked locations


def test_windows_cover_range_without_gaps() -> None:
    client, fake = client_returning(NOT_FOUND)
    client.locations(1, T0, T0 + timedelta(minutes=25))

    windows = [(p["date>"], p["date<"]) for _, p in fake.calls]
    assert windows == [
        ("2024-09-01T12:59:59", "2024-09-01T13:10:01"),
        ("2024-09-01T13:09:59", "2024-09-01T13:20:01"),
        ("2024-09-01T13:19:59", "2024-09-01T13:25:01"),
    ]


def test_results_trimmed_to_requested_range() -> None:
    start = T0 + timedelta(milliseconds=700)
    end = start + timedelta(minutes=5)
    rows = [
        loc("2024-09-01T13:00:00.500000+00:00"),  # before start
        loc("2024-09-01T13:00:00.800000+00:00"),
        loc("2024-09-01T13:05:00.600000+00:00"),
        loc("2024-09-01T13:05:00.900000+00:00"),  # after end
    ]
    client, _ = client_returning(ok(rows))

    samples = client.locations(1, start, end)

    assert [s.time for s in samples] == [
        T0 + timedelta(milliseconds=800),
        T0 + timedelta(minutes=5, milliseconds=600),
    ]


def test_boundary_sample_returned_once() -> None:
    boundary = loc("2024-09-01T13:10:00+00:00")
    client, _ = client_returning(ok([boundary]))  # every window "contains" it

    samples = client.locations(1, T0, T0 + timedelta(minutes=20))

    assert len(samples) == 1


def test_locations_typed_and_sorted() -> None:
    rows = [
        loc("2024-09-01T13:00:02+00:00", driver=1),
        loc("2024-09-01T13:00:01+00:00", driver=16, x=5, y=6),
        loc("2024-09-01T13:00:01+00:00", driver=1),
    ]
    client, _ = client_returning(ok(rows))

    samples = client.locations(1, T0, T0 + timedelta(minutes=5))

    assert [(s.time.second, s.driver) for s in samples] == [(1, 1), (1, 16), (2, 1)]
    assert samples[1] == LocationSample(T0 + timedelta(seconds=1), 16, 5, 6, 0)


def test_driver_filter_passed_through() -> None:
    client, fake = client_returning(NOT_FOUND)
    client.locations(1, T0, T0 + timedelta(minutes=5), driver=16)
    assert fake.calls[0][1]["driver_number"] == 16


def test_empty_range_makes_no_requests() -> None:
    client, fake = client_returning(NOT_FOUND)
    assert client.locations(1, T0, T0) == []
    assert fake.calls == []


# programmer errors


def test_naive_datetime_rejected() -> None:
    client, _ = client_returning(NOT_FOUND)
    naive = datetime(2024, 9, 1, 13, 0)
    with pytest.raises(ValueError, match="naive datetime"):
        client.locations(1, naive, naive + timedelta(minutes=5))


def test_end_before_start_rejected() -> None:
    client, _ = client_returning(NOT_FOUND)
    with pytest.raises(ValueError, match="before start"):
        client.locations(1, T0, T0 - timedelta(minutes=1))


def test_chunk_must_be_positive() -> None:
    with pytest.raises(ValueError, match="chunk must be positive"):
        OpenF1Client(FakeTransport(lambda _e, _p: NOT_FOUND), chunk=timedelta(0))
