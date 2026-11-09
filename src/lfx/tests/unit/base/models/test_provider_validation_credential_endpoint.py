"""Provider validation must preserve the operator credential destination policy."""

from unittest.mock import Mock

import pytest
from lfx.base.models.unified_models.credentials import validate_model_provider_key
from lfx.services.variable.request_scope import activate_no_env_fallback, reset_no_env_fallback

OPERATOR_KEY = "sk-test-operator-validation"  # pragma: allowlist secret
USER_KEY = "sk-test-user-validation"  # pragma: allowlist secret
CUSTOM_URL = "https://8.8.8.8/v1"


@pytest.fixture
def model_factory(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", OPERATOR_KEY)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.setattr("lfx.base.models.provider_ssrf.get_provider_credential_allowed_hosts", list)
    monkeypatch.setattr("lfx.utils.ssrf_protection.get_allowed_hosts", list)
    factory = Mock()
    monkeypatch.setattr("langchain_openai.ChatOpenAI", factory)
    return factory


def test_validation_refuses_server_key_with_user_endpoint(model_factory):
    with pytest.raises(ValueError, match="server-provisioned API credential") as error:
        validate_model_provider_key(
            "OpenAI", {"OPENAI_API_KEY": OPERATOR_KEY, "OPENAI_BASE_URL": CUSTOM_URL}, model_name="gpt-4o-mini"
        )

    model_factory.assert_not_called()
    assert OPERATOR_KEY not in str(error.value)


@pytest.mark.parametrize("env_name", ["OPENAI_BASE_URL", "OPENAI_API_BASE"])
def test_validation_checks_sdk_endpoint_fallback(monkeypatch, model_factory, env_name):
    monkeypatch.setenv(env_name, CUSTOM_URL)

    with pytest.raises(ValueError, match="server-provisioned API credential"):
        validate_model_provider_key("OpenAI", {"OPENAI_API_KEY": OPERATOR_KEY}, model_name="gpt-4o-mini")

    model_factory.assert_not_called()


def test_validation_keeps_default_provider_endpoint(model_factory):
    validate_model_provider_key("OpenAI", {"OPENAI_API_KEY": OPERATOR_KEY}, model_name="gpt-4o-mini")

    assert model_factory.call_args.kwargs["api_key"] == OPERATOR_KEY
    model_factory.return_value.invoke.assert_called_once_with("test")


def test_validation_keeps_user_key_with_custom_endpoint(model_factory):
    validate_model_provider_key(
        "OpenAI", {"OPENAI_API_KEY": USER_KEY, "OPENAI_BASE_URL": CUSTOM_URL}, model_name="gpt-4o-mini"
    )

    assert model_factory.call_args.kwargs["api_key"] == USER_KEY
    assert model_factory.call_args.kwargs["base_url"] == CUSTOM_URL


def test_validation_keeps_operator_allowlisted_endpoint(monkeypatch, model_factory):
    monkeypatch.setattr("lfx.base.models.provider_ssrf.get_provider_credential_allowed_hosts", lambda: ["8.8.8.8"])

    validate_model_provider_key(
        "OpenAI", {"OPENAI_API_KEY": OPERATOR_KEY, "OPENAI_BASE_URL": CUSTOM_URL}, model_name="gpt-4o-mini"
    )

    assert model_factory.call_args.kwargs["base_url"] == CUSTOM_URL


def test_validation_checks_explicit_endpoint_before_sdk_fallback(monkeypatch, model_factory):
    monkeypatch.setenv("OPENAI_BASE_URL", CUSTOM_URL)

    validate_model_provider_key(
        "OpenAI",
        {"OPENAI_API_KEY": OPERATOR_KEY, "OPENAI_BASE_URL": "https://api.openai.com/v1"},
        model_name="gpt-4o-mini",
    )

    assert model_factory.call_args.kwargs["base_url"] == "https://api.openai.com/v1"


def test_validation_respects_disabled_environment_fallback(monkeypatch, model_factory):
    monkeypatch.setenv("OPENAI_BASE_URL", CUSTOM_URL)
    token = activate_no_env_fallback(disabled=True)
    try:
        validate_model_provider_key("OpenAI", {"OPENAI_API_KEY": USER_KEY}, model_name="gpt-4o-mini")
    finally:
        reset_no_env_fallback(token)

    assert model_factory.call_args.kwargs["base_url"] == "https://api.openai.com/v1"
