.PHONY: fmt lint typecheck test check audit figures build export

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy

test:
	uv run pytest

check: lint typecheck test

audit:
	uv export --format requirements-txt --all-groups --no-emit-project -q -o .audit-requirements.txt
	uv run pip-audit --strict --disable-pip -r .audit-requirements.txt

figures:
	uv run python scripts/figures/track.py
	uv run python scripts/figures/openf1.py
	uv run python scripts/figures/phase0.py

build:
	rm -rf dist
	uv build

export:
	uv run python scripts/export_race.py --year 2024 --circuit Monza
