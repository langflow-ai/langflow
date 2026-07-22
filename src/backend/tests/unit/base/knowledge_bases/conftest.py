from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_opensearchpy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide the optional opensearch-py surface these unit tests patch.

    The default Langflow test environment does not install OpenSearch extras.
    These tests mock the client entirely, so a small import stub keeps the
    backend behavior covered without pulling opensearch-py into the base install.
    """
    if "opensearchpy" in sys.modules and sys.modules["opensearchpy"] is not None:
        return

    opensearchpy = ModuleType("opensearchpy")
    helpers = ModuleType("opensearchpy.helpers")
    exceptions = ModuleType("opensearchpy.exceptions")

    authentication_exception = type("AuthenticationException", (Exception,), {})
    authorization_exception = type("AuthorizationException", (Exception,), {})
    connection_error = type("ConnectionError", (Exception,), {})
    ssl_error = type("SSLError", (Exception,), {})

    opensearchpy.OpenSearch = MagicMock(name="OpenSearch")
    helpers.scan = MagicMock(name="scan")
    exceptions.AuthenticationException = authentication_exception
    exceptions.AuthorizationException = authorization_exception
    exceptions.ConnectionError = connection_error
    exceptions.SSLError = ssl_error
    opensearchpy.helpers = helpers
    opensearchpy.exceptions = exceptions

    monkeypatch.setitem(sys.modules, "opensearchpy", opensearchpy)
    monkeypatch.setitem(sys.modules, "opensearchpy.helpers", helpers)
    monkeypatch.setitem(sys.modules, "opensearchpy.exceptions", exceptions)
