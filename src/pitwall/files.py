"""Writing files so that a crash never leaves half of one."""

import os
import tempfile
from pathlib import Path


def write_atomic(path: Path, body: bytes) -> None:
    """Write body to a temp file next to path, then rename it over path in one step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # unique temp file per writer, so concurrent writes to one path can't collide
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
        os.replace(tmp, path)  # atomic rename: readers see the old file or the new one
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
