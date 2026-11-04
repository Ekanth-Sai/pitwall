"""Release notes for a tag: check the tag matches the package version, print its CHANGELOG section.
Run by .github/workflows/release.yml: uv run python scripts/release_notes.py v0.1.0
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_TAG = re.compile(r"v(?P<version>\d+\.\d+\.\d+)")
# Keep a Changelog: a release starts at "## [0.1.0] - 2026-11-03"
_RELEASE = re.compile(r"^## \[(?P<version>[^\]]+)\].*$", re.MULTILINE)
# a section ends at the next release heading or at the link definitions at the bottom
_END = re.compile(r"^(## |\[[^\]]+\]: )", re.MULTILINE)


class ReleaseError(Exception):
    """The tag, the package version and the changelog don't agree"""


def version_of(tag: str) -> str:
    match = _TAG.fullmatch(tag)
    if match is None:
        raise ReleaseError(f"tag {tag!r} is not vMAJOR.MINOR.PATCH")
    return match["version"]


def notes(changelog: str, version: str) -> str:
    """The body of the changelog section for version, without its heading."""
    for heading in _RELEASE.finditer(changelog):
        if heading["version"] == version:
            end = _END.search(changelog, heading.end() + 1)
            body = changelog[heading.end() : end.start() if end else len(changelog)].strip()
            if not body:
                raise ReleaseError(f"CHANGELOG.md has an empty section for {version}")
            return body
    raise ReleaseError(f"CHANGELOG.md has no section for {version}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: release_notes.py vMAJOR.MINOR.PATCH", file=sys.stderr)
        return 2
    try:
        version = version_of(argv[1])
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
        if version != project:
            raise ReleaseError(f"tag {argv[1]} but pyproject.toml says {project}")
        print(notes((ROOT / "CHANGELOG.md").read_text(), version))
    except ReleaseError as e:
        print(f"release_notes: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
