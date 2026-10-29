.PHONY: fmt lint typecheck test check audit

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
