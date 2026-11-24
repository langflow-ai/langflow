"""Connection checks use synthetic credentials and never contact providers."""

# ruff: noqa: S105, S106
from functools import partial
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from huggingface_hub import constants as huggingface_constants
from lfx_bundles.cloudflare.cloudflare import CloudflareWorkersAIEmbeddingsComponent
from lfx_bundles.huggingface.huggingface import HuggingFaceEndpointsComponent
from lfx_bundles.mistral.mistral import MistralAIModelComponent
from lfx_bundles.unstructured.unstructured import UnstructuredComponent


@pytest.fixture(autouse=True)
def enable_ssrf(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
    for name in ("HUGGINGFACEHUB_API_TOKEN", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_OIDC_RESOURCE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(huggingface_constants, "HF_TOKEN_PATH", str(tmp_path / "hf-token"))


@pytest.mark.parametrize("target", ["http://169.254.169.254/latest", "http://10.1.2.3/v1"])
@pytest.mark.parametrize("provider", ["mistral", "huggingface", "cloudflare", "unstructured"])
def test_rejects_blocked_target_before_sdk_construction(provider, target):
    if provider == "mistral":
        component = MistralAIModelComponent().set(api_key="synthetic", mistral_api_base=target)
        sdk_path = "lfx_bundles.mistral.mistral.ChatMistralAI"
        build = component.build_model
    elif provider == "huggingface":
        component = HuggingFaceEndpointsComponent().set(huggingfacehub_api_token="synthetic", inference_endpoint=target)
        sdk_path = "lfx_bundles.huggingface.huggingface.HuggingFaceEndpoint"
        build = component.build_model
    elif provider == "cloudflare":
        component = CloudflareWorkersAIEmbeddingsComponent().set(
            api_token="synthetic", account_id="account", api_base_url=target
        )
        sdk_path = "lfx_bundles.cloudflare.cloudflare.CompatibleCloudflareEmbeddings"
        build = component.build_embeddings
    else:
        component = UnstructuredComponent().set(api_key="synthetic", api_url=target)
        sdk_path = "lfx_bundles.unstructured.unstructured.UnstructuredLoader"
        build = partial(component.process_files, [SimpleNamespace(path="/unused")])
    with patch(sdk_path) as sdk, pytest.raises(ValueError, match=r"blocked|Could not connect"):
        build()
    sdk.assert_not_called()


@pytest.mark.parametrize("provider", ["mistral", "huggingface", "cloudflare", "unstructured"])
def test_rejects_environment_credential_to_unapproved_public_target(monkeypatch, provider):
    monkeypatch.setenv("SYNTHETIC_PROVIDER_TOKEN", "synthetic-environment-token")
    target = "https://example.com/api"
    if provider == "mistral":
        component = MistralAIModelComponent().set(api_key="synthetic-environment-token", mistral_api_base=target)
        sdk_path = "lfx_bundles.mistral.mistral.ChatMistralAI"
        build = component.build_model
    elif provider == "huggingface":
        component = HuggingFaceEndpointsComponent().set(
            huggingfacehub_api_token="synthetic-environment-token", inference_endpoint=target
        )
        sdk_path = "lfx_bundles.huggingface.huggingface.HuggingFaceEndpoint"
        build = component.build_model
    elif provider == "cloudflare":
        component = CloudflareWorkersAIEmbeddingsComponent().set(
            api_token="synthetic-environment-token", account_id="account", api_base_url=target
        )
        sdk_path = "lfx_bundles.cloudflare.cloudflare.CompatibleCloudflareEmbeddings"
        build = component.build_embeddings
    else:
        component = UnstructuredComponent().set(api_key="synthetic-environment-token", api_url=target)
        sdk_path = "lfx_bundles.unstructured.unstructured.UnstructuredLoader"
        build = partial(component.process_files, [SimpleNamespace(path="/unused")])
    with patch(sdk_path) as sdk, pytest.raises(ValueError, match=r"server-provisioned|Could not connect"):
        build()
    sdk.assert_not_called()


def test_unstructured_validates_additional_argument_url():
    component = UnstructuredComponent().set(api_key="synthetic", unstructured_args={"url": "http://169.254.169.254/"})
    with (
        patch("lfx_bundles.unstructured.unstructured.UnstructuredLoader") as sdk,
        pytest.raises(ValueError, match="blocked"),
    ):
        component.process_files([SimpleNamespace(path="/unused")])
    sdk.assert_not_called()


def test_unstructured_validates_environment_url(monkeypatch):
    monkeypatch.setenv("UNSTRUCTURED_URL", "http://169.254.169.254/")
    component = UnstructuredComponent().set(api_key="synthetic")
    with (
        patch("lfx_bundles.unstructured.unstructured.UnstructuredLoader") as sdk,
        pytest.raises(ValueError, match="blocked"),
    ):
        component.process_files([SimpleNamespace(path="/unused")])
    sdk.assert_not_called()


def test_huggingface_preserves_caller_key_on_allowed_endpoint(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "synthetic-server-token")
    component = HuggingFaceEndpointsComponent().set(
        huggingfacehub_api_token="synthetic-caller-token", inference_endpoint="https://example.com/inference"
    )
    with (
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["93.184.216.34"]),
        patch("lfx_bundles.huggingface.huggingface.HuggingFaceEndpoint") as sdk,
    ):
        component.build_model()
    assert sdk.call_args.kwargs["endpoint_url"] == "https://example.com/inference"
    assert sdk.call_args.kwargs["huggingfacehub_api_token"] == "synthetic-caller-token"


@pytest.mark.parametrize("source", ["HUGGINGFACEHUB_API_TOKEN", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "saved", "none"])
def test_huggingface_rejects_implicit_credentials_to_unapproved_target(monkeypatch, tmp_path, source):
    if source == "saved":
        (tmp_path / "hf-token").write_text("synthetic-server-token")
    elif source != "none":
        monkeypatch.setenv(source, "synthetic-server-token")
    component = HuggingFaceEndpointsComponent().set(
        huggingfacehub_api_token="", inference_endpoint="https://example.com/inference"
    )
    with (
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["93.184.216.34"]),
        patch("lfx_bundles.huggingface.huggingface.HuggingFaceEndpoint") as sdk,
        pytest.raises(ValueError, match="Could not connect"),
    ):
        component.build_model()
    sdk.assert_not_called()


@pytest.mark.parametrize("source", ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "saved", "none"])
@pytest.mark.parametrize("endpoint", ["default", "https://example.com/inference"])
def test_huggingface_preserves_implicit_auth_without_login(monkeypatch, tmp_path, source, endpoint):
    if source == "saved":
        (tmp_path / "hf-token").write_text("synthetic-server-token")
    elif source != "none":
        monkeypatch.setenv(source, "synthetic-server-token")
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "example.com")
    component = HuggingFaceEndpointsComponent().set(huggingfacehub_api_token="")
    if endpoint != "default":
        component.set(inference_endpoint=endpoint)
    with (
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["93.184.216.34"]),
        patch("huggingface_hub.login", side_effect=AssertionError("Login must remain implicit")) as login,
        patch("huggingface_hub.InferenceClient") as sync_client,
        patch("huggingface_hub.AsyncInferenceClient") as async_client,
    ):
        model = component.build_model()
    login.assert_not_called()
    assert sync_client.call_args.kwargs["token"] is None
    assert async_client.call_args.kwargs["token"] is None
    assert model.huggingfacehub_api_token == ""


@pytest.mark.parametrize(
    ("allowlist", "endpoint", "allowed"),
    [
        ("example.com:8443", "https://example.com:8443/inference", True),
        ("example.com:8443", "https://example.com:9443/inference", False),
        ("*.example.com", "https://models.example.com/inference", True),
        ("*.example.com", "https://example.com/inference", False),
        ("example.com", "https://example.com.attacker.test/inference", False),
        ("https://example.com", "https://example.com/inference", True),
        ("example.com", "http://example.com/inference", False),
        ("http://example.com", "http://example.com/inference", True),
    ],
)
def test_huggingface_implicit_auth_respects_operator_allowlist(monkeypatch, allowlist, endpoint, allowed):
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", allowlist)
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "example.com")
    component = HuggingFaceEndpointsComponent().set(huggingfacehub_api_token="", inference_endpoint=endpoint)
    with (
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["93.184.216.34"]),
        patch("huggingface_hub.login", side_effect=AssertionError("Login must remain implicit")) as login,
        patch("huggingface_hub.InferenceClient") as sync_client,
        patch("huggingface_hub.AsyncInferenceClient") as async_client,
    ):
        if allowed:
            component.build_model()
            assert sync_client.call_args.kwargs["token"] is None
            assert async_client.call_args.kwargs["token"] is None
        else:
            with pytest.raises(ValueError, match="Could not connect"):
                component.build_model()
            sync_client.assert_not_called()
            async_client.assert_not_called()
    login.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("explicit_key", "environment_key", "expected"),
    [
        ("", "synthetic-environment-token", "Bearer synthetic-environment-token"),
        ("synthetic-explicit-token", "synthetic-environment-token", "Bearer synthetic-explicit-token"),
        ("", None, None),
    ],
)
async def test_mistral_pinned_clients_use_effective_credential(monkeypatch, explicit_key, environment_key, expected):
    if environment_key is None:
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    else:
        monkeypatch.setenv("MISTRAL_API_KEY", environment_key)
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "example.com")
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    component = MistralAIModelComponent().set(api_key=explicit_key, mistral_api_base="https://example.com/v1")
    with (
        patch(
            "lfx_bundles.mistral.mistral.provider_httpx_client_kwargs",
            return_value=({"transport": transport}, {"transport": transport}),
        ),
        patch("lfx_bundles.mistral.mistral.ChatMistralAI") as sdk,
    ):
        component.build_model()
    sync_client = sdk.call_args.kwargs["client"]
    async_client = sdk.call_args.kwargs["async_client"]
    try:
        assert sync_client.headers.get("authorization") == expected
        assert async_client.headers.get("authorization") == expected
        assert sdk.call_args.kwargs["mistral_api_key"] == (explicit_key or environment_key)
    finally:
        sync_client.close()
        await async_client.aclose()


@pytest.mark.asyncio
async def test_mistral_configures_both_pinned_clients():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(respond)
    component = MistralAIModelComponent().set(
        api_key="synthetic-caller-token",  # pragma: allowlist secret
        mistral_api_base="https://example.com/v1",
    )
    with (
        patch(
            "lfx_bundles.mistral.mistral.provider_httpx_client_kwargs",
            return_value=({"transport": transport}, {"transport": transport}),
        ),
        patch("lfx_bundles.mistral.mistral.ChatMistralAI") as sdk,
    ):
        component.build_model()
    sync_client = sdk.call_args.kwargs["client"]
    async_client = sdk.call_args.kwargs["async_client"]
    sync_client.post("/chat/completions", json={})
    await async_client.post("/chat/completions", json={})
    assert str(requests[0].url) == "https://example.com/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer synthetic-caller-token"
    assert async_client.headers["authorization"] == "Bearer synthetic-caller-token"
    assert str(async_client.base_url) == "https://example.com/v1/"
    sync_client.close()
    await async_client.aclose()


def test_unstructured_pins_effective_endpoint_without_mutating_options():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    options = {"url": "https://example.com/partition", "strategy": "fast"}
    component = UnstructuredComponent().set(api_key="synthetic-caller-token", unstructured_args=options)
    with (
        patch(
            "lfx_bundles.unstructured.unstructured.provider_httpx_client_kwargs",
            return_value=({"transport": transport}, {}),
        ),
        patch("lfx_bundles.unstructured.unstructured.UnstructuredLoader") as loader,
        patch.object(component, "rollup_data", return_value=[]),
    ):
        loader.return_value.load.return_value = []
        component.process_files([SimpleNamespace(path="/unused", data=[])])
    assert "api_key" not in loader.call_args.kwargs
    assert "url" not in loader.call_args.kwargs
    assert loader.call_args.kwargs["client"].sdk_configuration.server_url == options["url"]
    assert options == {"url": "https://example.com/partition", "strategy": "fast"}
