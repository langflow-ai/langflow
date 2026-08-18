"""Pytest hooks for MrScraper tests (optional SDK may be absent in minimal envs)."""

import sys
from importlib.util import find_spec
from types import ModuleType


def pytest_configure() -> None:
    """Register a minimal ``mrscraper`` module when ``mrscraper-sdk`` is not installed."""
    if find_spec("mrscraper") is None:
        stub = ModuleType("mrscraper")
        stub.MrScraper = object
        sys.modules["mrscraper"] = stub
