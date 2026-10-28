"""Connection checks use synthetic credentials and never contact providers."""

# ruff: noqa: S105, S106
from functools import partial
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from lfx_bundles.cloudflare.cloudflare import CloudflareWorkersAIEmbeddingsComponent
from lfx_bundles.huggingface.huggingface import HuggingFaceEndpointsComponent
from lfx_bundles.mistral.mistral import MistralAIModelComponent
from lfx_bundles.unstructured.unstructured import UnstructuredComponent


@pytest.fixture(autouse=True)
def enable_ssrf(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)


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


def test_huggingface_preserves_caller_key_on_allowed_endpoint():
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
