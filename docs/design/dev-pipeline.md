# Development pipeline

```mermaid
flowchart TD
    A["You type code"] --> B["git commit"]
    B --> C{"pre-commit hooks<br/>local, ~seconds"}
    C -->|"ruff format, ruff check, mypy strict"| D{"All pass?"}
    D -->|"no"| E["Commit blocked:<br/>fix and retry"]
    E --> B
    D -->|"yes"| F["git push feature branch"]
    F --> G{"GitHub Actions CI<br/>clean Ubuntu VM"}
    G -->|"uv sync locked, ruff, mypy,<br/>pytest + coverage 85%+"| H{"CI green?"}
    H -->|"no"| I["Fix on the branch"]
    I --> B
    H -->|"yes"| J["Pull Request"]
    J --> K["Merge to main"]
```

**Why both stages:** pre-commit gives fast local feedback but can be skipped
and runs on my machine; CI runs on a clean VM from `uv.lock` and is the actual
gate. `main` only receives CI-green merges.

## Releases

```mermaid
flowchart TD
    A["Phase write-up merged"] --> B["Branch: bump the minor version,<br/>date the CHANGELOG section"]
    B --> C["PR, CI green, squash-merge"]
    C --> D["git tag vX.Y.Z on main, push the tag"]
    D --> E{"release.yml<br/>on the tag"}
    E -->|"tag not on main"| X["Fail"]
    E -->|"make check fails"| X
    E -->|"tag, pyproject.toml and CHANGELOG disagree"| X
    E --> F["uv build: wheel + sdist"]
    F --> G{"Wheel installs in a clean env<br/>and reports the tag's version?"}
    G -->|"no"| X
    G -->|"yes"| H["Signed build provenance"]
    H --> I["GitHub release: notes from CHANGELOG,<br/>wheel + sdist attached"]
```

- **Versions** follow SemVer: one minor version per phase (P0 is v0.1.0, P8 is v1.0.0), patches
  between phases. The only place a version is written is `[project] version` in `pyproject.toml`.
  `pitwall.__version__` reads it back from the installed package metadata, and
  `tests/test_package.py` checks the two agree.
- **Bumping:** `uv version --bump minor` (or `patch`) edits `pyproject.toml` and `uv.lock` together.
- **CHANGELOG.md** uses [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Work goes under
  `## [Unreleased]`; the release PR renames that to `## [X.Y.Z] - date` and opens a new empty
  `Unreleased`. Links inside a release section are absolute, because the same text becomes the
  GitHub release notes.
- **The tag is the trigger.** `release.yml` refuses to publish unless the tag is on `main`,
  `make check` passes, `scripts/release_notes.py` finds the tag's version in both `pyproject.toml`
  and `CHANGELOG.md`, and the built wheel installs and reports that version. A mistyped tag fails
  before anything is published.
- **Permissions:** only the release job can write (`contents: write` to create the release,
  `id-token` and `attestations` to sign provenance). CI stays read-only.
- **Provenance:** `gh attestation verify pitwall-X.Y.Z-py3-none-any.whl --repo Ekanth-Sai/pitwall`
  checks that a downloaded file was built by this workflow from this repo.
- No PyPI upload: releases live on GitHub only (GHCR images start at P6.R).

Measured for v0.1.0: wheel 17.6 KB (15 modules), sdist 14.9 KB.
