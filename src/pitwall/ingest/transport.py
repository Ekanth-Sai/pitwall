"""Transports: how bytes get from a data source to us."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Self

import httpx

from pitwall.errors import SourceError

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
            self._write(path, response.body)
        return response

    def _path(self, endpoint: str, params: Params) -> Path:
        key = json.dumps(params, sort_keys=True)
        digest = hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:16]
        return self._dir / endpoint / f"{digest}.json"

    @staticmethod
    def _write(path: Path, body: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # unique temp file per writer, so concurrent misses on one key can't collide
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(body)
            os.replace(tmp, path)  # atomic rename: a crash never leaves a half written file
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
