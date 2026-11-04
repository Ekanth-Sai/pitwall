import tomllib
from pathlib import Path

import pitwall

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_comes_from_pyproject() -> None:
    project = tomllib.loads(PYPROJECT.read_text())["project"]
    assert pitwall.__version__ == project["version"]
