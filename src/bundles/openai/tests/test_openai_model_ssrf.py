"""SSRF regression coverage for the OpenAI Chat Model base-URL field.

``openai_api_base`` is tenant-editable and is handed straight to the OpenAI SDK, which
then issues a server-side request to that host carrying the operator's stored provider
credential. These tests pin the connector SSRF policy onto that field.
"""

from unittest.mock import patch

import pytest
from lfx_openai.components.openai.openai import OpenAIEmbeddingsComponent
from lfx_openai.components.openai.openai_chat_model import OpenAIModelComponent

_FAKE_OPENAI_API_KEY = "sk-not-a-real-key"  # pragma: allowlist secret


def _component(base_url: str | None) -> OpenAIModelComponent:
    component = OpenAIModelComponent()
    component.openai_api_base = base_url
    component.api_key = _FAKE_OPENAI_API_KEY
    component.model_name = "gpt-4.1-nano"
    component.max_tokens = 10
    component.model_kwargs = {}
    component.json_mode = False
    component.temperature = 0.1
    component.seed = 1
    component.max_retries = 5
    component.timeout = 700
    return component


class TestOpenAIModelBaseUrlSSRF:
    @pytest.mark.parametrize(
        "blocked_url",
        [
            "http://169.254.169.254/latest/meta-data",
            "http://[fd00::1]/v1",
            "http://10.0.0.5:8000/v1",
            "http://192.168.1.10/v1",
            "http://172.16.0.9/v1",
        ],
    )
    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_block_internal_base_url(self, mock_chat_openai, blocked_url):
        """Cloud-metadata and RFC1918 base URLs must never reach the SDK."""
        component = _component(blocked_url)

        with pytest.raises(ValueError, match="SSRF Protection"):
            component.build_model()

        mock_chat_openai.assert_not_called()

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_block_non_http_base_url(self, mock_chat_openai):
        """A non-http(s) scheme is not a validatable connector URL and must be refused."""
        component = _component("file:///etc/passwd")

        with pytest.raises(ValueError, match="SSRF Protection"):
            component.build_model()

        mock_chat_openai.assert_not_called()

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_pin_http_clients_for_custom_base_url(self, mock_chat_openai):
        """An allowed custom endpoint still builds, but through SSRF-protected clients."""
        component = _component("http://127.0.0.1:1234/v1")

        component.build_model()

        kwargs = mock_chat_openai.call_args.kwargs
        assert kwargs["base_url"] == "http://127.0.0.1:1234/v1"
        assert "http_client" in kwargs
        assert "http_async_client" in kwargs

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_block_loopback_when_operator_disables_the_exemption(self, mock_chat_openai, monkeypatch):
        """Multi-tenant operators can close the local-model-server loopback exemption."""
        monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "false")
        component = _component("http://127.0.0.1:9999/v1")

        with pytest.raises(ValueError, match="SSRF Protection"):
            component.build_model()

        mock_chat_openai.assert_not_called()

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_leave_default_endpoint_untouched(self, mock_chat_openai):
        """No custom base URL means no behavior change: default endpoint, no injected clients."""
        component = _component(None)

        component.build_model()

        kwargs = mock_chat_openai.call_args.kwargs
        assert kwargs["base_url"] == "https://api.openai.com/v1"
        assert "http_client" not in kwargs
        assert "http_async_client" not in kwargs

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_respect_global_ssrf_kill_switch(self, mock_chat_openai, monkeypatch):
        """Operators who disable SSRF protection keep the previous unvalidated behavior."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")
        component = _component("http://10.0.0.5:8000/v1")

        component.build_model()

        assert mock_chat_openai.call_args.kwargs["base_url"] == "http://10.0.0.5:8000/v1"


def _embeddings_component(base_url: str | None) -> OpenAIEmbeddingsComponent:
    component = OpenAIEmbeddingsComponent()
    component.openai_api_base = base_url
    component.openai_api_key = _FAKE_OPENAI_API_KEY
    component.model = "text-embedding-3-small"
    component.client = None
    component.dimensions = None
    component.deployment = None
    component.openai_api_version = None
    component.openai_api_type = None
    component.openai_proxy = None
    component.embedding_ctx_length = 1536
    component.openai_organization = None
    component.chunk_size = 1000
    component.max_retries = 3
    component.request_timeout = None
    component.tiktoken_enable = True
    component.tiktoken_model_name = None
    component.show_progress_bar = False
    component.model_kwargs = {}
    component.skip_empty = False
    component.default_headers = None
    component.default_query = None
    return component


class TestOpenAIEmbeddingsBaseUrlSSRF:
    @pytest.mark.parametrize(
        "blocked_url",
        [
            "http://169.254.169.254/latest/meta-data",
            "http://10.0.0.5:8000/v1",
            "http://192.168.1.10/v1",
        ],
    )
    @patch("lfx_openai.components.openai.openai.OpenAIEmbeddings")
    def test_should_block_internal_base_url(self, mock_embeddings, blocked_url):
        """The embeddings component shares the field name and the credential-forwarding sink."""
        component = _embeddings_component(blocked_url)

        with pytest.raises(ValueError, match="SSRF Protection"):
            component.build_embeddings()

        mock_embeddings.assert_not_called()

    @patch("lfx_openai.components.openai.openai.OpenAIEmbeddings")
    def test_should_leave_default_endpoint_untouched(self, mock_embeddings):
        """No custom base URL means no injected clients."""
        component = _embeddings_component(None)

        component.build_embeddings()

        kwargs = mock_embeddings.call_args.kwargs
        assert kwargs["base_url"] is None
        assert "http_client" not in kwargs
