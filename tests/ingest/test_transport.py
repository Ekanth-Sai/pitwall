import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from pitwall.errors import SourceError
from pitwall.ingest.transport import CachedTransport, HttpTransport, Params, Response

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

    monkeypatch.setattr("pitwall.ingest.transport.os.replace", boom)
    cached = CachedTransport(StubTransport(Response(200, b"[]")), tmp_path)

    with pytest.raises(OSError, match="disk full"):
        cached.get("location", {})
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]
