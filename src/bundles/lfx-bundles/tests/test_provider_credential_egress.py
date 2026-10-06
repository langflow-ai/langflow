"""Custom provider URLs must not receive operator keys without approval."""

from importlib import import_module
from unittest.mock import patch

import httpx
import pytest

SERVER_KEY = "server-provider-test-key"
CUSTOM_URL = "https://provider-proxy.example"
PROVIDERS = [
    (
        "groq.groq",
        "GroqModel",
        "base_url",
        "api_key",
        "langchain_groq.ChatGroq",
        "GROQ_API_KEY",
        "https://api.groq.com",
    ),
    (
        "deepseek.deepseek",
        "DeepSeekModelComponent",
        "api_base",
        "api_key",
        "langchain_openai.ChatOpenAI",
        "OPENAI_API_KEY",
        "https://api.deepseek.com",
    ),
    (
        "aiml.aiml",
        "AIMLModelComponent",
        "aiml_api_base",
        "api_key",
        "lfx_bundles.aiml.aiml.ChatOpenAI",
        "OPENAI_API_KEY",
        "https://api.aimlapi.com/v2",
    ),
    (
        "sambanova.sambanova",
        "SambaNovaComponent",
        "base_url",
        "api_key",
        "lfx_bundles.sambanova.sambanova.ChatSambaNova",
        "SAMBANOVA_API_KEY",
        "https://api.sambanova.ai/v1",
    ),
    (
        "mistral.mistral_embeddings",
        "MistralAIEmbeddingsComponent",
        "endpoint",
        "mistral_api_key",
        "lfx_bundles.mistral.mistral_embeddings.MistralAIEmbeddings",
        "MISTRAL_API_KEY",
        "https://api.mistral.ai/v1/",
    ),
]


@pytest.fixture(autouse=True)
def operator_environment(monkeypatch):
    monkeypatch.setenv("PROVIDER_TEST_KEY", SERVER_KEY)
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "trusted.example")
    monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _host: ["93.184.216.34"])


@pytest.fixture(params=PROVIDERS, ids=[p[0] for p in PROVIDERS])
def provider(request):
    module, name, url_field, key_field, sdk, fallback, default_url = request.param
    cls = getattr(import_module(f"lfx_bundles.{module}"), name)
    component = cls(**{url_field: CUSTOM_URL, key_field: SERVER_KEY}, model_name="test-model")
    build = component.build_embeddings if key_field == "mistral_api_key" else component.build_model
    return component, build, url_field, key_field, sdk, fallback, default_url


def test_rejects_operator_credential_before_sdk(provider):
    _component, build, _url_field, _key_field, sdk, _fallback, _default = provider
    with patch(sdk) as client, pytest.raises(ValueError, match="server-provisioned API credential"):
        build()
    client.assert_not_called()


def test_allows_tenant_credential(provider):
    component, build, _url_field, key_field, sdk, _fallback, _default = provider
    setattr(component, key_field, "tenant-provider-test-key")
    with patch(sdk) as client:
        build()
    client.assert_called_once()


def test_preserves_canonical_default(provider):
    component, build, url_field, _key_field, sdk, _fallback, default = provider
    setattr(component, url_field, default)
    with patch(sdk) as client:
        build()
    client.assert_called_once()


def test_allows_operator_host_allowlist(provider, monkeypatch):
    _component, build, _url_field, _key_field, sdk, _fallback, _default = provider
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "provider-proxy.example")
    with patch(sdk) as client:
        build()
    client.assert_called_once()


@pytest.mark.parametrize(
    ("module", "name", "sdk", "env_var"),
    [
        ("groq.groq", "GroqModel", "langchain_groq.ChatGroq", "GROQ_API_KEY"),
        ("deepseek.deepseek", "DeepSeekModelComponent", "langchain_openai.ChatOpenAI", "OPENAI_API_KEY"),
        ("aiml.aiml", "AIMLModelComponent", "lfx_bundles.aiml.aiml.ChatOpenAI", "OPENAI_API_KEY"),
        (
            "sambanova.sambanova",
            "SambaNovaComponent",
            "lfx_bundles.sambanova.sambanova.ChatSambaNova",
            "SAMBANOVA_API_KEY",
        ),
    ],
)
@pytest.mark.parametrize("api_key", [None, ""])
def test_rejects_sdk_environment_fallback(module, name, sdk, env_var, api_key, monkeypatch):
    monkeypatch.setenv(env_var, SERVER_KEY)
    cls = getattr(import_module(f"lfx_bundles.{module}"), name)
    url_field = {"DeepSeekModelComponent": "api_base", "AIMLModelComponent": "aiml_api_base"}.get(name, "base_url")
    component = cls(**{url_field: CUSTOM_URL}, api_key=api_key, model_name="test-model")
    with patch(sdk) as client, pytest.raises(ValueError, match="server-provisioned API credential"):
        component.build_model()
    client.assert_not_called()


def test_deepseek_refresh_rejects_before_http_request():
    from lfx_bundles.deepseek.deepseek import DeepSeekModelComponent

    component = DeepSeekModelComponent(api_base=CUSTOM_URL, api_key=SERVER_KEY)
    with (
        patch("lfx_bundles.deepseek.deepseek.ssrf_safe_httpx_get") as request,
        pytest.raises(ValueError, match="server-provisioned API credential"),
    ):
        component.get_models()
    request.assert_not_called()


def test_sambanova_custom_tenant_endpoint_reaches_sdk():
    from lfx_bundles.sambanova.sambanova import SambaNovaComponent

    component = SambaNovaComponent(base_url=CUSTOM_URL, api_key="tenant-provider-test-key", model_name="test-model")
    model = component.build_model()
    assert model.sambanova_api_base == CUSTOM_URL
    assert str(model.client._client.base_url).rstrip("/") == CUSTOM_URL
    from lfx.utils.ssrf_transport import SSRFProtectedSyncTransport, SSRFProtectedTransport

    assert isinstance(model.client._client._client._transport, SSRFProtectedSyncTransport)
    assert isinstance(model.async_client._client._client._transport, SSRFProtectedTransport)
    assert model.client._client._client.follow_redirects is False
    assert model.async_client._client._client.follow_redirects is False


def test_sambanova_secondary_environment_key_is_guarded(monkeypatch):
    from lfx_bundles.sambanova.sambanova import SambaNovaComponent

    monkeypatch.setenv("SAMBANOVA_API_KEY", SERVER_KEY)
    component = SambaNovaComponent(base_url=CUSTOM_URL, api_key="tenant-provider-test-key", model_name="test-model")
    with (
        patch("lfx_bundles.sambanova.sambanova.ChatSambaNova") as client,
        pytest.raises(ValueError, match="server-provisioned API credential"),
    ):
        component.build_model()
    client.assert_not_called()


@pytest.mark.parametrize("env_var", ["SAMBANOVA_API_BASE", "SAMBA_NOVA_BASE_URL"])
def test_sambanova_preserves_sdk_endpoint_environment(env_var, monkeypatch):
    from lfx_bundles.sambanova.sambanova import SambaNovaComponent

    monkeypatch.delenv("SAMBANOVA_API_BASE", raising=False)
    monkeypatch.delenv("SAMBA_NOVA_BASE_URL", raising=False)
    monkeypatch.setenv(env_var, CUSTOM_URL)
    component = SambaNovaComponent(base_url="", api_key="tenant-provider-test-key", model_name="test-model")
    with patch("lfx_bundles.sambanova.sambanova.ChatSambaNova") as client:
        component.build_model()
    assert client.call_args.kwargs["base_url"] == CUSTOM_URL
    assert "http_client" in client.call_args.kwargs


@pytest.mark.parametrize(
    "endpoint", ["https://api.sambanova.ai/v1/chat/completions", "https://api.sambanova.ai/v1/chat/completions/"]
)
def test_sambanova_preserves_legacy_canonical_endpoint(endpoint):
    from lfx_bundles.sambanova.sambanova import SambaNovaComponent

    component = SambaNovaComponent(base_url=endpoint, api_key=SERVER_KEY, model_name="test-model")
    with patch("lfx_bundles.sambanova.sambanova.ChatSambaNova") as client:
        component.build_model()
    assert client.call_args.kwargs["base_url"] == "https://api.sambanova.ai/v1"
    assert "http_client" not in client.call_args.kwargs


@pytest.mark.parametrize("url_source", ["base_url", "SAMBANOVA_API_BASE", "SAMBA_NOVA_BASE_URL"])
@pytest.mark.parametrize("endpoint_suffix", ["", "/chat/completions", "/chat/completions/"])
@pytest.mark.parametrize("api_key", ["tenant-provider-test-key", SERVER_KEY])
@pytest.mark.asyncio
async def test_sambanova_custom_completion_request_path(url_source, endpoint_suffix, api_key, monkeypatch):
    """Legacy completion URLs produce one completion path in both SDK clients."""
    from lfx_bundles.sambanova.sambanova import SambaNovaComponent

    monkeypatch.delenv("SAMBANOVA_API_BASE", raising=False)
    monkeypatch.delenv("SAMBA_NOVA_BASE_URL", raising=False)
    monkeypatch.delenv("SAMBANOVA_API_KEY", raising=False)
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "provider-proxy.example")
    base_url = f"{CUSTOM_URL}/tenant/v1"
    endpoint = base_url + endpoint_suffix
    if url_source != "base_url":
        monkeypatch.setenv(url_source, endpoint)
    component = SambaNovaComponent(
        base_url=endpoint if url_source == "base_url" else "", api_key=api_key, model_name="test-model"
    )
    model = component.build_model()
    requests = []

    def respond(request: httpx.Request, **_kwargs) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "test-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "test-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            },
        )

    try:
        with patch("httpx.Client.send", side_effect=respond), patch("httpx.AsyncClient.send", side_effect=respond):
            assert model.invoke("hello").content == "ok"
            assert (await model.ainvoke("hello")).content == "ok"
    finally:
        model.client._client.close()
        await model.async_client._client.close()

    assert requests == [f"{base_url}/chat/completions"] * 2
