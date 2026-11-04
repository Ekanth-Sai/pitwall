"""Pitwall: a live F1 race tracker."""

from importlib.metadata import version

# one source of truth: [project] version in pyproject.toml, read back from the installed metadata
__version__ = version("pitwall")
