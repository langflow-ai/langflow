"""Credential destination checks for unified OpenAI model construction."""

from unittest.mock import Mock

import pytest
from lfx.base.models import unified_models
from lfx.base.models.unified_models import instantiation

_OPERATOR_KEY = "sk-test-operator-credential"  # pragma: allowlist secret
_CUSTOM_URL = "https://models.example/v1"
_MODEL = [{"provider": "OpenAI", "name": "gpt-4o-mini", "metadata": {}}]


@pytest.fixture
def model_factory(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", _OPERATOR_KEY)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
    monkeypatch.setattr("lfx.base.models.provider_ssrf.get_provider_credential_allowed_hosts", list)
    monkeypatch.setattr(unified_models, "get_all_variables_for_provider", lambda *_args: {})
    monkeypatch.setattr(instantiation, "ssrf_protected_openai_clients_for_url", lambda _url: {})
    monkeypatch.setattr("lfx.base.models.model_remediation.cached_overrides", lambda *_args: {})
    factory = Mock()
    monkeypatch.setattr(unified_models, "get_model_class", lambda _name: factory)
    return factory


@pytest.mark.parametrize(
    "source", ["provider", "environment", "legacy-environment", "override", "cached-override", "alias", "sdk-key"]
)
def test_server_key_cannot_reach_custom_endpoint(monkeypatch, model_factory, source):
    overrides = None
    if source == "provider":
        monkeypatch.setattr(
            unified_models, "get_all_variables_for_provider", lambda *_args: {"OPENAI_BASE_URL": _CUSTOM_URL}
        )
    elif source in {"environment", "legacy-environment"}:
        monkeypatch.setenv("OPENAI_API_BASE" if source == "legacy-environment" else "OPENAI_BASE_URL", _CUSTOM_URL)
    elif source == "cached-override":
        monkeypatch.setattr(
            "lfx.base.models.model_remediation.cached_overrides", lambda *_args: {"base_url": _CUSTOM_URL}
        )
    else:
        overrides = {"openai_api_base" if source == "alias" else "base_url": _CUSTOM_URL}
        if source == "sdk-key":
            overrides["api_key"] = None

    with pytest.raises(ValueError, match="server-provisioned API credential") as error:
        instantiation.get_llm(_MODEL, user_id=None, overrides=overrides)

    model_factory.assert_not_called()
    assert _OPERATOR_KEY not in str(error.value)


@pytest.mark.parametrize("base_url", [None, "https://api.openai.com/v1", "https://api.openai.com/v1/"])
def test_server_key_can_reach_default_endpoint(model_factory, base_url):
    overrides = {"base_url": base_url} if base_url is not None else None

    instantiation.get_llm(_MODEL, user_id=None, overrides=overrides)

    assert model_factory.call_args.kwargs["api_key"] == _OPERATOR_KEY


def test_server_key_can_reach_operator_allowed_endpoint(monkeypatch, model_factory):
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "models.example")
    monkeypatch.setattr(
        "lfx.base.models.provider_ssrf.get_provider_credential_allowed_hosts", lambda: ["models.example"]
    )

    instantiation.get_llm(_MODEL, user_id=None, overrides={"base_url": _CUSTOM_URL})

    assert model_factory.call_args.kwargs["base_url"] == _CUSTOM_URL
    assert model_factory.call_args.kwargs["api_key"] == _OPERATOR_KEY


def test_caller_key_can_reach_custom_endpoint(model_factory):
    instantiation.get_llm(_MODEL, user_id=None, api_key="sk-test-caller-key", overrides={"base_url": _CUSTOM_URL})

    assert model_factory.call_args.kwargs["base_url"] == _CUSTOM_URL
    assert model_factory.call_args.kwargs["api_key"] == "sk-test-caller-key"  # pragma: allowlist secret


@pytest.mark.parametrize("source", ["alias", "cached-alias", "environment", "legacy-environment"])
def test_resolved_endpoint_uses_protected_clients(monkeypatch, model_factory, source):
    protected_clients = {"http_client": Mock(), "http_async_client": Mock()}
    protect = Mock(return_value=protected_clients)
    monkeypatch.setattr(instantiation, "ssrf_protected_openai_clients_for_url", protect)
    overrides = None
    if source == "alias":
        overrides = {"openai_api_base": _CUSTOM_URL}
    elif source == "cached-alias":
        monkeypatch.setattr(
            "lfx.base.models.model_remediation.cached_overrides", lambda *_args: {"openai_api_base": _CUSTOM_URL}
        )
    else:
        monkeypatch.setenv("OPENAI_API_BASE" if source == "legacy-environment" else "OPENAI_BASE_URL", _CUSTOM_URL)

    instantiation.get_llm(_MODEL, user_id=None, api_key="sk-test-caller-key", overrides=overrides)

    protect.assert_called_once_with(_CUSTOM_URL)
    kwargs = model_factory.call_args.kwargs
    assert kwargs["base_url"] == _CUSTOM_URL
    assert kwargs["http_client"] is protected_clients["http_client"]
    assert kwargs["http_async_client"] is protected_clients["http_async_client"]


def test_final_overridden_key_is_checked(monkeypatch, model_factory):
    monkeypatch.setattr(unified_models, "get_api_key_for_provider", lambda *_args: "sk-test-caller-key")

    with pytest.raises(ValueError, match="server-provisioned API credential"):
        instantiation.get_llm(_MODEL, user_id=None, overrides={"base_url": _CUSTOM_URL, "api_key": _OPERATOR_KEY})

    model_factory.assert_not_called()


@pytest.mark.parametrize("api_key_param", ["api_key", "openai_api_key"])
def test_legacy_provider_metadata_cannot_skip_credential_check(model_factory, api_key_param):
    model = [
        {
            "provider": "Legacy OpenAI Compatible",
            "name": "test-model",
            "metadata": {"model_class": "ChatOpenAI", "api_key_param": api_key_param},
        }
    ]

    with pytest.raises(ValueError, match="server-provisioned API credential"):
        instantiation.get_llm(model, user_id=None, api_key="OPENAI_API_KEY", overrides={"base_url": _CUSTOM_URL})

    model_factory.assert_not_called()


def test_openrouter_keeps_its_server_defined_default_endpoint(model_factory):
    model = [{"provider": "OpenRouter", "name": "test-model", "metadata": {}}]

    instantiation.get_llm(model, user_id=None, api_key="OPENAI_API_KEY")

    assert model_factory.call_args.kwargs["base_url"] == "https://openrouter.ai/api/v1"


def test_trimmed_server_key_cannot_reach_custom_endpoint(monkeypatch, model_factory):
    monkeypatch.setenv("OPENAI_API_KEY", f" {_OPERATOR_KEY}\n")

    with pytest.raises(ValueError, match="server-provisioned API credential"):
        instantiation.get_llm(_MODEL, user_id=None, overrides={"base_url": _CUSTOM_URL})

    model_factory.assert_not_called()
