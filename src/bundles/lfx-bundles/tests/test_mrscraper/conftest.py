"""Pytest hooks for MrScraper tests (optional SDK may be absent in minimal envs)."""

import sys
from importlib.util import find_spec
from types import ModuleType


def pytest_configure() -> None:
    """Register a minimal ``mrscraper`` module when ``mrscraper-sdk`` is not installed.

    The stub carries a marker so the signature-conformance tests can tell it
    apart from the real SDK and skip rather than assert against a placeholder.
    CI installs ``lfx-bundles[all-no-torch]`` before running this suite, so the
    real package is present there and those tests do execute.
    """
    if find_spec("mrscraper") is None:
        stub = ModuleType("mrscraper")
        stub.MrScraper = object
        stub.__lfx_test_stub__ = True
        sys.modules["mrscraper"] = stub
