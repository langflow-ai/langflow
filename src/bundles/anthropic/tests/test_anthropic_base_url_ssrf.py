"""SSRF regression coverage for the Anthropic model component's API URL field.

``base_url`` is tenant-editable and is handed to the Anthropic SDK, which then issues a
server-side request to that host carrying the operator's stored provider credential.
"""

from unittest.mock import patch

import pytest
from lfx.base.models.anthropic_constants import DEFAULT_ANTHROPIC_API_URL
from lfx.utils.ssrf_transport import SSRFProtectedSyncTransport, SSRFProtectedTransport
from lfx_anthropic.components.anthropic.anthropic import AnthropicModelComponent

_FAKE_ANTHROPIC_API_KEY = "sk-ant-not-a-real-key"  # pragma: allowlist secret

BLOCKED_URLS = [
    "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.5:8000",
    "http://192.168.1.10",
    "http://172.16.0.9",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


def _component(base_url: str | None) -> AnthropicModelComponent:
    component = AnthropicModelComponent()
    component.base_url = base_url
    component.api_key = _FAKE_ANTHROPIC_API_KEY
    component.model_name = "claude-3-5-sonnet-latest"
    component.max_tokens = 100
    component.temperature = 0.1
    component.stream = False
    component.tool_model_enabled = False
    return component


class TestAnthropicBaseUrlSSRF:
    @pytest.mark.parametrize("blocked_url", BLOCKED_URLS)
    @patch("lfx_anthropic.anthropic_chat_model.ChatAnthropicThinkingCompat")
    def test_should_block_internal_base_url_in_build_model(self, mock_chat, blocked_url):
        """Cloud-metadata and RFC1918 API URLs must never reach the SDK."""
        component = _component(blocked_url)

        with pytest.raises(ValueError, match="SSRF Protection"):
            component.build_model()

        mock_chat.assert_not_called()

    @pytest.mark.parametrize("blocked_url", BLOCKED_URLS)
    def test_should_block_internal_base_url_in_get_models(self, blocked_url):
        """The tool-capability probe builds its own client and must be guarded too."""
        component = _component(blocked_url)

        with pytest.raises(ValueError, match="SSRF Protection"):
            component.get_models(tool_model_enabled=True)

    @patch("lfx_anthropic.anthropic_chat_model.ChatAnthropicThinkingCompat")
    def test_should_leave_default_endpoint_untouched(self, mock_chat):
        """The provider default is server-chosen, so it stays a no-op."""
        component = _component(DEFAULT_ANTHROPIC_API_URL)

        component.build_model()

        assert mock_chat.call_args.kwargs["anthropic_api_url"] == DEFAULT_ANTHROPIC_API_URL

    @patch("lfx_anthropic.anthropic_chat_model.ChatAnthropicThinkingCompat")
    def test_should_respect_global_ssrf_kill_switch(self, mock_chat, monkeypatch):
        """Operators who disable SSRF protection keep the previous unvalidated behavior."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")
        component = _component("http://10.0.0.5:8000")

        component.build_model()

        assert mock_chat.call_args.kwargs["anthropic_api_url"] == "http://10.0.0.5:8000"

    def test_should_install_dns_pinned_clients_for_custom_endpoint(self, monkeypatch):
        monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _hostname: ["93.184.216.34"])
        component = _component("https://anthropic-proxy.example")

        model = component.build_model()

        assert isinstance(model._client._client._transport, SSRFProtectedSyncTransport)
        assert isinstance(model._async_client._client._transport, SSRFProtectedTransport)
        assert model._client._client._transport.pinned_ips == {"anthropic-proxy.example": ["93.184.216.34"]}
        assert model._async_client._client._transport.pinned_ips == {"anthropic-proxy.example": ["93.184.216.34"]}

    def test_should_allow_explicitly_allowlisted_loopback(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")
        component = _component("http://127.0.0.1:8000")

        model = component.build_model()

        assert model.anthropic_api_url == "http://127.0.0.1:8000"
