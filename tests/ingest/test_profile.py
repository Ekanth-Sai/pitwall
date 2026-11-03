import pytest

from pitwall.errors import SchemaError
from pitwall.ingest.profile import EndpointProfile, json_type


def row(date: str, driver: int | None = 16, **fields: object) -> dict[str, object]:
    base: dict[str, object] = {"date": f"2024-09-01T13:00:{date}+00:00"}
    if driver is not None:
        base["driver_number"] = driver
    return {**base, **fields}


def test_fields_counted_by_json_type() -> None:
    rows = [row("00", gap=1.5), row("04", gap="+1 LAP"), row("08", gap=None), row("12")]
    gap = {f.name: f for f in EndpointProfile.of("intervals", rows).fields}["gap"]
    assert gap.types == {"float": 1, "string": 1, "null": 1, "absent": 1}
    assert gap.nulls == 2
    assert gap.example == 1.5


def test_fields_sorted_by_name() -> None:
    profile = EndpointProfile.of("pit", [row("00", lap_number=5, b=True)])
    assert [f.name for f in profile.fields] == ["b", "date", "driver_number", "lap_number"]


def test_all_null_field_has_no_example() -> None:
    (stop,) = [
        f for f in EndpointProfile.of("pit", [row("00", stop=None)]).fields if f.name == "stop"
    ]
    assert stop.example is None


def test_gaps_per_driver_in_time_order() -> None:
    # two drivers interleaved and out of order: gaps are within each driver only
    rows = [row("04", 1), row("00", 16), row("00", 1), row("10", 16), row("05", 16)]
    profile = EndpointProfile.of("intervals", rows)
    assert sorted(profile.gaps) == [4.0, 5.0, 5.0]
    assert profile.median_gap == 5.0


def test_feed_without_drivers_is_one_stream() -> None:
    rows = [row("00", None), row("30", None), row("59", None)]
    assert EndpointProfile.of("weather", rows).gaps == (30.0, 29.0)


def test_rows_without_dates_have_no_gaps() -> None:
    profile = EndpointProfile.of("stints", [{"driver_number": 16, "lap_start": 1}])
    assert profile.gaps == ()
    assert profile.median_gap is None


def test_empty_endpoint() -> None:
    profile = EndpointProfile.of("pit", [])
    assert (profile.rows, profile.fields, profile.median_gap) == (0, (), None)


@pytest.mark.parametrize("date", ["yesterday", 1725195600])
def test_unreadable_date_raises_schema_error(date: object) -> None:
    with pytest.raises(SchemaError, match="weather: unreadable date"):
        EndpointProfile.of("weather", [{"date": date}, {"date": date}])


@pytest.mark.parametrize(
    ("value", "name"),
    [
        (None, "null"),
        (True, "bool"),
        (3, "int"),
        (3.5, "float"),
        ("s", "string"),
        ([], "array"),
        ({}, "object"),
    ],
)
def test_json_type_names(value: object, name: str) -> None:
    assert json_type(value) == name


def test_json_type_rejects_non_json_values() -> None:
    with pytest.raises(ValueError, match="not a decoded JSON value: tuple"):
        json_type((1, 2))
