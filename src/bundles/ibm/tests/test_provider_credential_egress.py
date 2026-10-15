"""Watsonx keeps its canonical regions and protects custom credential destinations."""

from unittest.mock import patch

import pytest
from lfx_ibm.components.ibm.watsonx import WatsonxAIComponent
from lfx_ibm.components.ibm.watsonx_embeddings import WatsonxEmbeddingsComponent

SERVER_KEY = "server-watsonx-test-key"
CUSTOM_URL = "https://watsonx-proxy.example"


@pytest.fixture(autouse=True)
def operator_environment(monkeypatch):
    monkeypatch.setenv("WATSONX_API_KEY", SERVER_KEY)
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "trusted.example")
    monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _host: ["93.184.216.34"])


@pytest.fixture(params=[WatsonxAIComponent, WatsonxEmbeddingsComponent])
def watsonx(request):
    cls = request.param
    endpoint_field = "base_url" if cls is WatsonxAIComponent else "url"
    instance = cls(**{endpoint_field: CUSTOM_URL}, api_key=SERVER_KEY, project_id="project", space_id="")
    build = instance.build_model if cls is WatsonxAIComponent else instance.build_embeddings
    sdk_name = "ChatWatsonx" if cls is WatsonxAIComponent else "WatsonxEmbeddings"
    return instance, build, endpoint_field, f"{cls.__module__}.{sdk_name}"


def test_rejects_operator_key_before_sdk(watsonx):
    _instance, build, _field, sdk = watsonx
    with patch(sdk) as client, pytest.raises(ValueError, match="server-provisioned API credential"):
        build()
    client.assert_not_called()


def test_preserves_all_canonical_regions(watsonx):
    instance, build, field, sdk = watsonx
    for region in instance._urls:
        setattr(instance, field, region)
        with patch(sdk) as client:
            build()
        assert client.call_args.kwargs["url"] == region


def test_allows_tenant_credential(watsonx):
    instance, build, _field, sdk = watsonx
    instance.api_key = "tenant-watsonx-test-key"  # pragma: allowlist secret
    with patch(sdk) as client:
        build()
    client.assert_called_once()


def test_allows_operator_host_allowlist(watsonx, monkeypatch):
    _instance, build, _field, sdk = watsonx
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "watsonx-proxy.example")
    with patch(sdk) as client:
        build()
    client.assert_called_once()


@pytest.mark.parametrize(
    "env_var", ["WATSONX_TOKEN", "WATSONX_PASSWORD", "USER_ACCESS_TOKEN", "RUNTIME_ENV_ACCESS_TOKEN_FILE"]
)
def test_rejects_sdk_secondary_environment_credential(watsonx, monkeypatch, env_var):
    instance, build, _field, sdk = watsonx
    instance.api_key = "tenant-watsonx-test-key"  # pragma: allowlist secret
    monkeypatch.setenv(env_var, "operator-secondary-credential")
    with patch(sdk) as client, pytest.raises(ValueError, match="server-provisioned API credential"):
        build()
    client.assert_not_called()


@pytest.mark.parametrize("api_key", [None])
def test_rejects_absent_api_key_when_operator_key_exists(watsonx, api_key):
    instance, build, _field, sdk = watsonx
    instance.api_key = api_key
    with patch(sdk) as client, pytest.raises(ValueError, match="server-provisioned API credential"):
        build()
    client.assert_not_called()
