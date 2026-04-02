"""Watsonx Orchestrate local development URL and auth helpers."""

import pytest
from langflow.services.adapters.deployment.watsonx_orchestrate.client import resolve_wxo_authenticator
from langflow.services.adapters.deployment.watsonx_orchestrate.local_dev import (
    is_wxo_local_instance_url,
    resolve_wxo_local_bearer_token,
)
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.models.deployment_provider_account.utils import (
    check_provider_url_allowed,
    validate_provider_url,
)
from lfx.services.adapters.deployment.exceptions import AuthSchemeError


class _Info:
    field_name = "provider_url"


def test_validate_provider_url_rejects_http_without_local_dev_flag(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_DEV", raising=False)
    with pytest.raises(ValueError, match="https"):
        validate_provider_url("http://localhost:4321/", _Info())


def test_validate_provider_url_accepts_http_localhost_when_local_dev(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    out = validate_provider_url("http://LOCALHOST:4321/orchestrate", _Info())
    assert out == "http://localhost:4321/orchestrate"


def test_check_provider_url_allowed_localhost_when_local_dev(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    check_provider_url_allowed("http://127.0.0.1:4321/", DeploymentProviderKey.WATSONX_ORCHESTRATE)


def test_check_provider_url_allowed_rejects_localhost_without_flag(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_DEV", raising=False)
    with pytest.raises(ValueError, match="not allowed"):
        check_provider_url_allowed("http://localhost:4321/", DeploymentProviderKey.WATSONX_ORCHESTRATE)


def test_is_wxo_local_instance_url():
    assert is_wxo_local_instance_url("http://localhost:1/x") is True
    assert is_wxo_local_instance_url("https://api.foo.ibm.com/x") is False


def test_resolve_wxo_local_bearer_token_prefers_env(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.setenv("WXO_MCSP_LOCAL_TOKEN", "from-env")
    assert resolve_wxo_local_bearer_token(api_key="eyJignored") == "from-env"


def test_resolve_wxo_local_bearer_token_falls_back_to_jwt_api_key(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.delenv("WXO_MCSP_LOCAL_TOKEN", raising=False)
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.e30.sig"
    assert resolve_wxo_local_bearer_token(api_key=jwt_like) == jwt_like


def test_resolve_wxo_authenticator_local_uses_static_jwt(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.setenv("WXO_MCSP_LOCAL_TOKEN", "test-jwt-token")
    auth = resolve_wxo_authenticator("http://localhost:4321", api_key="unused")
    assert auth.token_manager.get_token() == "test-jwt-token"


def test_resolve_wxo_authenticator_local_requires_bearer(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.delenv("WXO_MCSP_LOCAL_TOKEN", raising=False)
    with pytest.raises(AuthSchemeError, match="WXO_MCSP_LOCAL_TOKEN"):
        resolve_wxo_authenticator("http://127.0.0.1:1", api_key="not-a-jwt")


def test_resolve_wxo_authenticator_cloud_still_uses_mcsp(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_DEV", raising=False)
    auth = resolve_wxo_authenticator("https://api.dl.watson-orchestrate.ibm.com/instances/x", api_key="k")
    assert auth.__class__.__name__ == "MCSPAuthenticator"
