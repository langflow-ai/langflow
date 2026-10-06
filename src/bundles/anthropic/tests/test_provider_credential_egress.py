"""Protect Anthropic builds and model refresh from operator credential egress."""

from unittest.mock import patch

import pytest
from lfx.base.models.anthropic_constants import DEFAULT_ANTHROPIC_API_URL
from lfx_anthropic import AnthropicModelComponent

SERVER_KEY = "server-anthropic-test-key"
CUSTOM_URL = "https://anthropic-proxy.example"


@pytest.fixture(autouse=True)
def operator_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SERVER_KEY)
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "trusted.example")
    monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _host: ["93.184.216.34"])


def component(base_url=CUSTOM_URL, api_key=SERVER_KEY):
    return AnthropicModelComponent(base_url=base_url, api_key=api_key, model_name="claude-3-5-sonnet-latest")


def test_rejects_operator_key_before_model_sdk():
    with (
        patch("lfx_anthropic.anthropic_chat_model.ChatAnthropicThinkingCompat") as client,
        pytest.raises(ValueError, match="server-provisioned API credential"),
    ):
        component().build_model()
    client.assert_not_called()


@pytest.mark.parametrize("tool_model_enabled", [False, True])
@pytest.mark.parametrize("api_key", [SERVER_KEY, None])
def test_refresh_rejects_before_discovery_or_capability_probe(tool_model_enabled, api_key):
    with (
        patch("anthropic.Anthropic") as discovery,
        patch("langchain_anthropic.chat_models.ChatAnthropic") as client,
        pytest.raises(ValueError, match="server-provisioned API credential"),
    ):
        component(api_key=api_key).get_models(tool_model_enabled=tool_model_enabled)
    discovery.assert_not_called()
    client.assert_not_called()


@pytest.mark.parametrize("base_url", [DEFAULT_ANTHROPIC_API_URL, None, ""])
def test_default_endpoint_accepts_operator_key(base_url):
    with patch("lfx_anthropic.anthropic_chat_model.ChatAnthropicThinkingCompat") as client:
        component(base_url).build_model()
    assert client.call_args.kwargs["anthropic_api_url"] == DEFAULT_ANTHROPIC_API_URL


def test_tenant_key_accepts_custom_endpoint():
    with patch("lfx_anthropic.anthropic_chat_model.ChatAnthropicThinkingCompat") as client:
        component(api_key="tenant-anthropic-test-key").build_model()  # pragma: allowlist secret
    client.assert_called_once()


def test_operator_allowlist_accepts_custom_endpoint(monkeypatch):
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "anthropic-proxy.example")
    with patch("lfx_anthropic.anthropic_chat_model.ChatAnthropicThinkingCompat") as client:
        component().build_model()
    client.assert_called_once()


def test_capability_probe_keeps_custom_endpoint_pinned():
    from types import SimpleNamespace

    from anthropic import Anthropic
    from lfx.utils.ssrf_transport import SSRFProtectedSyncTransport, SSRFProtectedTransport

    instance = component(api_key="tenant-anthropic-test-key")
    probed = []

    def supports_tools(model):
        probed.append(model)
        assert isinstance(model._client._client._transport, SSRFProtectedSyncTransport)
        assert isinstance(model._async_client._client._transport, SSRFProtectedTransport)
        assert model._client._client.follow_redirects is False
        assert model._async_client._client.follow_redirects is False
        return True

    with (
        patch("anthropic.Anthropic", wraps=Anthropic) as discovery,
        patch(
            "anthropic.resources.models.Models.list",
            return_value=SimpleNamespace(data=[SimpleNamespace(id="custom-test-model")]),
        ),
        patch.object(instance, "supports_tool_calling", supports_tools),
    ):
        models = instance.get_models(tool_model_enabled=True)

    assert "custom-test-model" in models
    assert probed
    assert discovery.call_args_list[0].kwargs["base_url"] == DEFAULT_ANTHROPIC_API_URL


@pytest.mark.parametrize("method", ["build_model", "get_models"])
def test_secondary_sdk_auth_token_is_guarded(method, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "operator-auth-token")
    instance = component(api_key="tenant-anthropic-test-key")
    with (
        patch("anthropic.Anthropic") as discovery,
        patch("lfx_anthropic.anthropic_chat_model.ChatAnthropicThinkingCompat") as client,
        pytest.raises(ValueError, match="server-provisioned API credential"),
    ):
        getattr(instance, method)()
    discovery.assert_not_called()
    client.assert_not_called()
