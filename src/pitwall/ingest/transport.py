"""Transports: how bytes get from a data source to us."""

import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Self

import httpx

from pitwall.errors import SourceError
from pitwall.files import write_atomic

Params = dict[str, str | int]


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes


class Transport(Protocol):
    def get(self, endpoint: str, params: Params) -> Response: ...


class HttpTransport:
    """Real HTTP via httpx. Network failures become SourceError; status codes are returned"""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    @classmethod
    def create(cls, base_url: str, timeout: float = 60.0) -> Self:
        return cls(httpx.Client(base_url=base_url, timeout=timeout))

    def get(self, endpoint: str, params: Params) -> Response:
        try:
            r = self._client.get(endpoint, params=params)
        except httpx.HTTPError as e:
            raise SourceError(f"GET {endpoint} failed: {e}") from e
        return Response(status=r.status_code, body=r.content)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class PacedTransport:
    """Spaces requests at least interval seconds apart. OpenF1 allows 3 a second, and answered
    the 5th in 1.3 s with 429.

    Goes under the cache, so cached runs never wait. P2.8 replaces it with a token bucket.
    """

    def __init__(
        self,
        inner: Transport,
        interval: float = 0.4,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if interval < 0:
            raise ValueError(f"interval must be >= 0, got {interval}")
        self._inner = inner
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._last = -math.inf  # so the first request never waits

    def get(self, endpoint: str, params: Params) -> Response:
        wait = self._last + self._interval - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last = self._clock()
        return self._inner.get(endpoint, params)


class CachedTransport:
    """Caches 200 responses on disk. Errors and 404s are not cached."""

    def __init__(self, inner: Transport, cache_dir: Path) -> None:
        self._inner = inner
        self._dir = cache_dir

    def get(self, endpoint: str, params: Params) -> Response:
        path = self._path(endpoint, params)
        if path.exists():
            return Response(status=200, body=path.read_bytes())
        response = self._inner.get(endpoint, params)
        if response.status == 200:
            write_atomic(path, response.body)
        return response

    def _path(self, endpoint: str, params: Params) -> Path:
        key = json.dumps(params, sort_keys=True)
        digest = hashlib.sha256(key.encode(), usedforsecurity=False).hexdigest()[:16]
        return self._dir / endpoint / f"{digest}.json"
