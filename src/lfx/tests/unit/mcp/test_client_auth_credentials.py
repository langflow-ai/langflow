"""Environment API keys are optional for clients serving authenticated requests."""

import pytest
from lfx.mcp.client import LangflowClient


def test_stdio_client_uses_environment_key_by_default(monkeypatch):
    monkeypatch.setenv("LANGFLOW_API_KEY", "configured-key")

    assert LangflowClient()._headers()["x-api-key"] == "configured-key"


@pytest.mark.parametrize("api_key", [None, ""])
def test_request_client_does_not_inherit_environment_key(monkeypatch, api_key):
    monkeypatch.setenv("LANGFLOW_API_KEY", "configured-key")

    client = LangflowClient(api_key=api_key, use_env_api_key=False)

    assert client._headers() == {"Content-Type": "application/json"}


def test_request_client_preserves_explicit_key(monkeypatch):
    monkeypatch.setenv("LANGFLOW_API_KEY", "configured-key")

    client = LangflowClient(api_key="caller-key", use_env_api_key=False)

    assert client._headers()["x-api-key"] == "caller-key"
