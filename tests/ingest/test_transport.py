import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from pitwall.errors import SourceError
from pitwall.ingest.transport import (
    CachedTransport,
    HttpTransport,
    PacedTransport,
    Params,
    Response,
)

Handler = Callable[[httpx.Request], httpx.Response]


def make_http(handler: Handler) -> tuple[HttpTransport, httpx.Client]:
    client = httpx.Client(
        base_url="https://example.test/v1/", transport=httpx.MockTransport(handler)
    )
    return HttpTransport(client), client


class StubTransport:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.calls: list[tuple[str, Params]] = []

    def get(self, endpoint: str, params: Params) -> Response:
        self.calls.append((endpoint, dict(params)))
        return self.response


# HttpTransport


def test_http_returns_status_and_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/location"
        assert request.url.params["session_key"] == "9590"
        return httpx.Response(200, content=b"[]")

    transport, _ = make_http(handler)
    assert transport.get("location", {"session_key": 9590}) == Response(200, b"[]")


def test_http_returns_error_status_without_raising() -> None:
    transport, _ = make_http(lambda _: httpx.Response(401))
    assert transport.get("location", {}).status == 401


def test_http_wraps_network_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Name or service not known", request=request)

    transport, _ = make_http(handler)
    with pytest.raises(SourceError, match="GET location failed") as exc_info:
        transport.get("location", {})
    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)


def test_http_context_manager_closes_client() -> None:
    transport, client = make_http(lambda _: httpx.Response(200))
    with transport:
        pass
    assert client.is_closed


# PacedTransport


class FakeClock:
    """Time that only moves when the transport sleeps, so waits are exact."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def paced(clock: FakeClock, interval: float = 0.4) -> tuple[PacedTransport, StubTransport]:
    inner = StubTransport(Response(200, b"[]"))
    return PacedTransport(inner, interval, clock=clock, sleep=clock.sleep), inner


def test_paced_first_request_does_not_wait() -> None:
    clock = FakeClock()
    transport, inner = paced(clock)
    assert transport.get("location", {"session_key": 1}) == Response(200, b"[]")
    assert clock.sleeps == []
    assert inner.calls == [("location", {"session_key": 1})]


def test_paced_back_to_back_requests_wait_the_interval() -> None:
    clock = FakeClock()
    transport, _ = paced(clock)
    transport.get("location", {})
    transport.get("location", {})
    transport.get("location", {})
    assert clock.sleeps == pytest.approx([0.4, 0.4])


def test_paced_waits_only_for_what_is_left() -> None:
    clock = FakeClock()
    transport, _ = paced(clock)
    transport.get("location", {})
    clock.now += 0.3  # the caller spent 0.3 s on something else
    transport.get("location", {})
    clock.now += 1.0
    transport.get("location", {})
    assert clock.sleeps == pytest.approx([0.1])


def test_paced_rejects_negative_interval() -> None:
    with pytest.raises(ValueError, match="interval must be >= 0"):
        PacedTransport(StubTransport(Response(200, b"")), -0.1)


# CachedTransport


def test_cache_hit_skips_inner(tmp_path: Path) -> None:
    inner = StubTransport(Response(200, b'[{"a": 1}]'))
    cached = CachedTransport(inner, tmp_path)

    first = cached.get("location", {"session_key": 1})
    second = cached.get("location", {"session_key": 1})

    assert first == second == Response(200, b'[{"a": 1}]')
    assert len(inner.calls) == 1


def test_cache_key_ignores_param_order(tmp_path: Path) -> None:
    inner = StubTransport(Response(200, b"[]"))
    cached = CachedTransport(inner, tmp_path)

    cached.get("location", {"a": 1, "b": 2})
    cached.get("location", {"b": 2, "a": 1})

    assert len(inner.calls) == 1


def test_cache_distinguishes_params(tmp_path: Path) -> None:
    inner = StubTransport(Response(200, b"[]"))
    cached = CachedTransport(inner, tmp_path)

    cached.get("location", {"a": 1})
    cached.get("location", {"a": 2})

    assert len(inner.calls) == 2


@pytest.mark.parametrize("status", [404, 401, 500])
def test_cache_never_stores_non_200(tmp_path: Path, status: int) -> None:
    inner = StubTransport(Response(status, json.dumps({"detail": "x"}).encode()))
    cached = CachedTransport(inner, tmp_path)

    cached.get("location", {})
    cached.get("location", {})

    assert len(inner.calls) == 2
    assert not any(tmp_path.rglob("*.json"))


def test_cache_write_leaves_no_temp_files(tmp_path: Path) -> None:
    cached = CachedTransport(StubTransport(Response(200, b"[]")), tmp_path)
    cached.get("location", {})
    assert [p.suffix for p in tmp_path.rglob("*") if p.is_file()] == [".json"]


def test_create_builds_working_transport() -> None:
    with HttpTransport.create("https://example.test/v1/") as transport:
        assert isinstance(transport, HttpTransport)


def test_failed_write_cleans_up_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("pitwall.files.os.replace", boom)
    cached = CachedTransport(StubTransport(Response(200, b"[]")), tmp_path)

    with pytest.raises(OSError, match="disk full"):
        cached.get("location", {})
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]
