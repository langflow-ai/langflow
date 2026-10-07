"""Azure endpoints must be trusted before server credentials reach the SDK."""

from unittest.mock import patch

import pytest
from lfx.utils.ssrf_transport import SSRFProtectedSyncTransport, SSRFProtectedTransport
from lfx_azure import AzureChatOpenAIComponent, AzureOpenAIEmbeddingsComponent

SERVER_KEY = "server-azure-test-key"
CUSTOM_URL = "https://azure-proxy.example"


@pytest.fixture(autouse=True)
def operator_environment(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", SERVER_KEY)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_AD_TOKEN", raising=False)
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "trusted.example")
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _host: ["93.184.216.34"])


@pytest.fixture(params=[AzureChatOpenAIComponent, AzureOpenAIEmbeddingsComponent])
def azure(request):
    cls = request.param
    component = cls(azure_endpoint=CUSTOM_URL, azure_deployment="deployment", api_key=SERVER_KEY)
    method = component.build_model if cls is AzureChatOpenAIComponent else component.build_embeddings
    sdk_name = "AzureChatOpenAI" if cls is AzureChatOpenAIComponent else "AzureOpenAIEmbeddings"
    return component, method, f"{cls.__module__}.{sdk_name}"


@pytest.mark.parametrize("api_key", [SERVER_KEY, None, ""])
def test_rejects_operator_key_before_sdk(azure, api_key):
    component, build, sdk = azure
    component.api_key = api_key
    with patch(sdk) as client, pytest.raises(ValueError, match="server-provisioned API credential"):
        build()
    client.assert_not_called()


def test_allows_tenant_key_with_pinned_clients(azure):
    component, build, sdk = azure
    component.api_key = "tenant-azure-test-key"  # pragma: allowlist secret
    with patch(sdk) as client:
        build()
    kwargs = client.call_args.kwargs
    assert isinstance(kwargs["http_client"]._transport, SSRFProtectedSyncTransport)
    assert isinstance(kwargs["http_async_client"]._transport, SSRFProtectedTransport)
    assert kwargs["http_client"]._transport.pinned_ips == {"azure-proxy.example": ["93.184.216.34"]}


def test_allows_operator_endpoint_without_trusting_tenant_endpoint(azure, monkeypatch):
    component, build, sdk = azure
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", CUSTOM_URL)
    with patch(sdk) as client:
        build()
    assert client.call_args.kwargs["azure_endpoint"] == CUSTOM_URL
    component.azure_endpoint = None
    with patch(sdk) as client:
        build()
    assert client.call_args.kwargs["azure_endpoint"] == CUSTOM_URL
    component.azure_endpoint = "https://foreign.example"
    with patch(sdk) as client, pytest.raises(ValueError, match="server-provisioned API credential"):
        build()
    client.assert_not_called()


def test_allows_operator_host_allowlist(azure, monkeypatch):
    _component, build, sdk = azure
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "azure-proxy.example")
    with patch(sdk) as client:
        build()
    client.assert_called_once()


def test_rejects_sdk_ad_token_even_with_tenant_api_key(azure, monkeypatch):
    component, build, sdk = azure
    component.api_key = "tenant-azure-test-key"  # pragma: allowlist secret
    monkeypatch.setenv("AZURE_OPENAI_AD_TOKEN", "operator-ad-token")
    with patch(sdk) as client, pytest.raises(ValueError, match="server-provisioned API credential"):
        build()
    client.assert_not_called()


def test_rejects_private_endpoint_before_sdk(azure, monkeypatch):
    monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _host: ["169.254.169.254"])
    component, build, sdk = azure
    component.api_key = "tenant-azure-test-key"  # pragma: allowlist secret
    component.azure_endpoint = "http://169.254.169.254/latest/meta-data"
    with patch(sdk) as client, pytest.raises(ValueError, match="SSRF Protection"):
        build()
    client.assert_not_called()
