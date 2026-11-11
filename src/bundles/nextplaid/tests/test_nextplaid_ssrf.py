"""Apply the shared connector policy before NextPlaid opens a connection."""

import sys
from types import ModuleType
from unittest.mock import Mock

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_nextplaid import NextPlaidVectorStoreComponent


@pytest.fixture
def store_factory(monkeypatch):
    """Replace the optional SDK constructor while retaining the real connector policy."""
    # The optional SDK is replaced only at the network boundary. The component
    # and shared destination policy run unchanged.
    factory = Mock()
    package = ModuleType("langchain_plaid")
    vectorstores = ModuleType("langchain_plaid.vectorstores")
    vectorstores.NextPlaidVectorStore = factory
    vectorstores.plaid = ModuleType("langchain_plaid.vectorstores.plaid")
    vectorstores.plaid.requests = object()
    monkeypatch.setitem(sys.modules, "langchain_plaid", package)
    monkeypatch.setitem(sys.modules, "langchain_plaid.vectorstores", vectorstores)
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "false")
    monkeypatch.setattr("lfx.utils.ssrf_protection.get_allowed_hosts", list)
    return factory


@pytest.mark.parametrize("url", ["http://10.20.0.1", "http://169.254.169.254", "http://127.0.0.1", "file:///etc/hosts"])
def test_blocked_destination_never_constructs_client(store_factory, url):
    """Blocked targets must fail before the SDK can connect."""
    component = NextPlaidVectorStoreComponent(url=url, embedding=object(), _session_id="test-session")

    with pytest.raises(SSRFProtectionError):
        component.build_vector_store()

    store_factory.assert_not_called()


def test_public_destination_reaches_client(store_factory):
    """Public destinations retain the ordinary component behavior."""
    component = NextPlaidVectorStoreComponent(url="https://8.8.8.8", embedding=object(), _session_id="test-session")

    assert component.build_vector_store() is store_factory.return_value
    assert store_factory.call_args.kwargs["url"] == "https://8.8.8.8"


def test_operator_allowlisted_destination_reaches_client(monkeypatch, store_factory):
    """An operator can still permit a private connector destination."""
    monkeypatch.setattr("lfx.utils.ssrf_protection.get_allowed_hosts", lambda: ["10.20.0.1"])
    component = NextPlaidVectorStoreComponent(url="http://10.20.0.1", embedding=object(), _session_id="test-session")

    assert component.build_vector_store() is store_factory.return_value
