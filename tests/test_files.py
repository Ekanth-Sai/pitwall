from pathlib import Path

import pytest

from pitwall.files import write_atomic


def test_write_atomic_creates_folders_and_replaces_the_old_file(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b.json"
    write_atomic(path, b"old")
    write_atomic(path, b"new")
    assert path.read_bytes() == b"new"
    assert [p.name for p in path.parent.iterdir()] == ["b.json"]  # no temp files left


def test_failed_write_keeps_the_old_file_and_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object) -> None:
        raise OSError("disk full")

    path = tmp_path / "b.json"
    write_atomic(path, b"old")
    monkeypatch.setattr("pitwall.files.os.replace", boom)
    with pytest.raises(OSError, match="disk full"):
        write_atomic(path, b"new")
    assert path.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["b.json"]
