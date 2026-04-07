"""Pytest hooks for MrScraper tests (optional SDK may be absent in minimal envs)."""

import sys
from types import ModuleType


def pytest_configure() -> None:
    """Register a minimal ``mrscraper`` module when ``mrscraper-sdk`` is not installed."""
    if "mrscraper" not in sys.modules:
        stub = ModuleType("mrscraper")
        stub.MrScraper = object
        sys.modules["mrscraper"] = stub
