import pytest
from release_notes import ReleaseError, main, notes, version_of

import pitwall

CHANGELOG = """# Changelog

## [Unreleased]

## [0.2.0] - 2026-12-13

### Added
- Replay in the browser

## [0.1.0] - 2026-11-03

### Added
- Track outline

[Unreleased]: https://example.com/compare/v0.2.0...HEAD
[0.2.0]: https://example.com/v0.2.0
"""


def test_notes_are_the_section_body() -> None:
    assert notes(CHANGELOG, "0.2.0") == "### Added\n- Replay in the browser"


def test_last_section_stops_at_the_link_definitions() -> None:
    assert notes(CHANGELOG, "0.1.0") == "### Added\n- Track outline"


def test_missing_version_is_an_error() -> None:
    with pytest.raises(ReleaseError, match=r"no section for 0\.3\.0"):
        notes(CHANGELOG, "0.3.0")


def test_empty_section_is_an_error() -> None:
    with pytest.raises(ReleaseError, match="empty section for Unreleased"):
        notes(CHANGELOG, "Unreleased")


@pytest.mark.parametrize(("tag", "version"), [("v0.1.0", "0.1.0"), ("v12.0.3", "12.0.3")])
def test_tag_gives_version(tag: str, version: str) -> None:
    assert version_of(tag) == version


@pytest.mark.parametrize("tag", ["0.1.0", "v0.1", "v0.1.0-rc1", "v0.1.0 ", "release"])
def test_tag_must_be_v_major_minor_patch(tag: str) -> None:
    with pytest.raises(ReleaseError, match=r"not vMAJOR\.MINOR\.PATCH"):
        version_of(tag)


def test_main_prints_the_notes_for_the_current_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["release_notes.py", f"v{pitwall.__version__}"]) == 0
    assert capsys.readouterr().out.strip()


def test_main_rejects_a_tag_that_does_not_match_the_package(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["release_notes.py", "v99.0.0"]) == 1
    assert "but pyproject.toml says" in capsys.readouterr().err


def test_main_needs_exactly_one_tag(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["release_notes.py"]) == 2
    assert "usage" in capsys.readouterr().err
