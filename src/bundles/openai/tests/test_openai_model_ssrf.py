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
    def test_should_pin_http_clients_for_custom_base_url(self, mock_chat_openai, monkeypatch):
        """An allowed custom endpoint still builds, but through SSRF-protected clients."""
        monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _hostname: ["93.184.216.34"])
        component = _component("https://provider.example/v1")

        component.build_model()

        kwargs = mock_chat_openai.call_args.kwargs
        assert kwargs["base_url"] == "https://provider.example/v1"
        assert "http_client" in kwargs
        assert "http_async_client" in kwargs

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_block_loopback_by_default(self, mock_chat_openai):
        """Provider credentials must not reach a server-local listener under defaults."""
        component = _component("http://127.0.0.1:9999/v1")

        with pytest.raises(ValueError, match="SSRF Protection"):
            component.build_model()

        mock_chat_openai.assert_not_called()

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_allow_explicitly_allowlisted_loopback(self, mock_chat_openai, monkeypatch):
        """A single-tenant operator can explicitly trust a local provider host."""
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")
        component = _component("http://127.0.0.1:1234/v1")

        component.build_model()

        assert mock_chat_openai.call_args.kwargs["base_url"] == "http://127.0.0.1:1234/v1"

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

    @patch("lfx_openai.components.openai.openai.OpenAIEmbeddings")
    def test_should_block_loopback_by_default(self, mock_embeddings):
        component = _embeddings_component("http://127.0.0.1:9999/v1")

        with pytest.raises(ValueError, match="SSRF Protection"):
            component.build_embeddings()

        mock_embeddings.assert_not_called()


@patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
def test_chat_model_explicit_default_endpoint_is_still_a_no_op(mock_chat_openai):
    """A saved configuration that spells out the default endpoint must not change behaviour.

    The existing coverage only exercises an unset base URL. A stored flow that explicitly
    carries ``https://api.openai.com/v1`` must take the same no-op path, otherwise the
    default endpoint gets DNS-pinned, redirect-free clients it never had before.
    """
    component = _component("https://api.openai.com/v1")

    component.build_model()

    kwargs = mock_chat_openai.call_args.kwargs
    assert kwargs["base_url"] == "https://api.openai.com/v1"
    assert "http_client" not in kwargs
    assert "http_async_client" not in kwargs


@patch("lfx_openai.components.openai.openai.OpenAIEmbeddings")
def test_embeddings_explicit_default_endpoint_is_still_a_no_op(mock_embeddings):
    """Same for the embeddings component, which previously omitted ``default_url``."""
    component = _embeddings_component("https://api.openai.com/v1")

    component.build_embeddings()

    kwargs = mock_embeddings.call_args.kwargs
    assert "http_client" not in kwargs
    assert "http_async_client" not in kwargs


_OPERATOR_ENV_KEY = "sk-operator-only-canary-f0e1d2c3"  # pragma: allowlist secret


class TestOpenAICredentialEgress:
    """Credential-egress guard for the OpenAI components (H1-4000668 / LE-2670).

    A key provisioned in the server environment (which the tenant may use but
    never read) must not be forwarded to a tenant-chosen endpoint.
    """

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_block_env_sourced_key_to_custom_host(self, mock_chat_openai, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
        component = _component("https://attacker.example.com/v1")
        component.api_key = _OPERATOR_ENV_KEY  # resolved from the server environment

        with pytest.raises(ValueError, match="server-provisioned API credential"):
            component.build_model()

        mock_chat_openai.assert_not_called()

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_allow_env_sourced_key_to_default_endpoint(self, mock_chat_openai, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)
        component = _component(None)
        component.api_key = _OPERATOR_ENV_KEY

        component.build_model()

        assert mock_chat_openai.call_args.kwargs["base_url"] == "https://api.openai.com/v1"

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_allow_env_sourced_key_to_operator_allowlisted_host(self, mock_chat_openai, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "llm-gateway.corp.example")
        monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _hostname: ["93.184.216.34"])
        component = _component("https://llm-gateway.corp.example/v1")
        component.api_key = _OPERATOR_ENV_KEY

        component.build_model()

        assert mock_chat_openai.call_args.kwargs["base_url"] == "https://llm-gateway.corp.example/v1"

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_should_allow_tenant_owned_key_to_custom_host(self, mock_chat_openai, monkeypatch):
        """Bring-your-own-key flows against custom endpoints are unaffected."""
        monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _hostname: ["93.184.216.34"])
        component = _component("https://provider.example/v1")  # _FAKE_OPENAI_API_KEY is not in env

        component.build_model()

        assert mock_chat_openai.call_args.kwargs["base_url"] == "https://provider.example/v1"

    @patch("lfx_openai.components.openai.openai.OpenAIEmbeddings")
    def test_embeddings_should_block_env_sourced_key_to_custom_host(self, mock_embeddings, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
        component = _embeddings_component("https://attacker.example.com/v1")
        component.openai_api_key = _OPERATOR_ENV_KEY

        with pytest.raises(ValueError, match="server-provisioned API credential"):
            component.build_embeddings()

        mock_embeddings.assert_not_called()


class TestOpenAIAbsentKeyCredentialEgress:
    """An absent component key is not an absent credential (LE-2670 follow-up).

    Both components normalize an empty key to ``api_key=None`` before handing it to the
    SDK, and the OpenAI SDK answers ``None`` by loading ``OPENAI_API_KEY`` out of the
    server process environment -- while keeping the tenant's ``base_url``. Leaving the
    field blank was therefore a way around the credential guard.
    """

    CUSTOM_URL = "https://attacker.example.com/v1"

    @pytest.fixture(autouse=True)
    def _no_allowlist(self, monkeypatch):
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)

    @pytest.mark.parametrize("absent", [None, ""])
    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_chat_should_block_absent_key_when_env_would_supply_one(self, mock_chat_openai, absent, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)
        component = _component(self.CUSTOM_URL)
        component.api_key = absent

        with pytest.raises(ValueError, match=r"falls back to \$OPENAI_API_KEY"):
            component.build_model()

        mock_chat_openai.assert_not_called()

    @pytest.mark.parametrize("absent", [None, ""])
    @patch("lfx_openai.components.openai.openai.OpenAIEmbeddings")
    def test_embeddings_should_block_absent_key_when_env_would_supply_one(self, mock_embeddings, absent, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)
        component = _embeddings_component(self.CUSTOM_URL)
        component.openai_api_key = absent

        with pytest.raises(ValueError, match=r"falls back to \$OPENAI_API_KEY"):
            component.build_embeddings()

        mock_embeddings.assert_not_called()

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_chat_should_allow_absent_key_when_no_env_fallback_exists(self, mock_chat_openai, monkeypatch):
        """With nothing for the SDK to resolve, there is no operator credential to protect."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _hostname: ["93.184.216.34"])
        component = _component("https://provider.example/v1")
        component.api_key = None

        component.build_model()

        assert mock_chat_openai.call_args.kwargs["base_url"] == "https://provider.example/v1"

    @patch("lfx_openai.components.openai.openai_chat_model.ChatOpenAI")
    def test_chat_should_allow_absent_key_to_an_allowlisted_host(self, mock_chat_openai, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "llm-gateway.corp.example")
        monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _hostname: ["93.184.216.34"])
        component = _component("https://llm-gateway.corp.example/v1")
        component.api_key = None

        component.build_model()

        assert mock_chat_openai.call_args.kwargs["base_url"] == "https://llm-gateway.corp.example/v1"

    def test_the_sdk_really_does_resolve_the_operator_key_for_a_custom_host(self, monkeypatch):
        """Pin the SDK behavior the guard exists to defend against.

        This builds the real ``ChatOpenAI`` -- no network call is made, the client is only
        constructed and inspected -- to show that ``api_key=None`` puts the operator's
        environment key into the Authorization header while keeping the tenant's host. If a
        future langchain-openai stops doing this, this test fails and the guard's premise
        can be revisited rather than silently over-blocking.
        """
        from langchain_openai import ChatOpenAI

        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)

        client = ChatOpenAI(model="gpt-4.1-nano", api_key=None, base_url=self.CUSTOM_URL).root_client

        assert _OPERATOR_ENV_KEY in str(client.auth_headers)
        assert str(client.base_url).startswith(self.CUSTOM_URL)

    def test_the_guard_runs_before_that_client_is_ever_built(self, monkeypatch):
        """The same scenario through the component, with the SDK left unmocked."""
        monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_ENV_KEY)
        component = _component(self.CUSTOM_URL)
        component.api_key = None

        with pytest.raises(ValueError, match="server-provisioned API credential"):
            component.build_model()
