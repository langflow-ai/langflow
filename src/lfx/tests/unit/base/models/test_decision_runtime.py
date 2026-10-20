"""Decision execution rejects denied/configuration-invalid requests before inference."""

from unittest.mock import Mock

import pytest
from lfx.base.models import unified_models
from lfx.base.models.decisions import providers
from lfx.base.models.decisions.runtime import evaluate_decision
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest, DecisionResult
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
)
from lfx.services.variable.request_scope import (
    activate_no_env_fallback,
    activate_request_variables,
    reset_no_env_fallback,
    reset_request_variables,
)


@pytest.fixture
def execution(monkeypatch):
    request = DecisionRequest(kind="boolean", question="Is this a complaint?", context="My payment failed.")
    model = {"provider": "OpenAI", "name": "gpt-6-luna"}
    policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"openai"}),
        allowed_provider_ids=frozenset({"openai"}),
    )
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy)
    transport = Mock(
        return_value=DecisionResult(
            kind="boolean",
            provider="OpenAI",
            model="gpt-6-luna",
            probability_true=0.8,
        )
    )
    monkeypatch.setattr(providers, "evaluate_provider", transport)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("LANGFLOW_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("LANGFLOW_OPENAI_API_BASE", raising=False)
    return request, model, transport


def test_explicit_key_uses_canonical_metadata_and_typed_policy(execution):
    request, model, transport = execution
    model["metadata"] = {"model_type": "llm", "base_url": "https://attacker.invalid", "capabilities": []}
    result = evaluate_decision(request, model=[model], api_key="sk-explicit-test")
    assert result.probability_true == 0.8
    transport.assert_called_once_with("OpenAI", "gpt-6-luna", request, api_key="sk-explicit-test", timeout=60)


@pytest.mark.parametrize("blocked", [frozenset(), frozenset({"openai::decision::gpt-6-luna"})])
def test_policy_denial_precedes_any_credential_lookup(execution, monkeypatch, blocked):
    request, model, transport = execution
    snapshot = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"openai"}),
        allowed_provider_ids=frozenset({"openai"}) if blocked else frozenset(),
        blocked_model_keys=blocked,
    )
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: snapshot)
    credentials = Mock(side_effect=AssertionError("Credentials must not be read"))
    monkeypatch.setattr(unified_models, "get_all_variables_for_provider", credentials)
    monkeypatch.setattr(unified_models, "get_api_key_for_provider", credentials)
    with pytest.raises(ModelProviderPolicyError):
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    credentials.assert_not_called()
    transport.assert_not_called()


def test_no_env_fallback_blocks_server_key(execution, monkeypatch):
    request, model, transport = execution
    monkeypatch.setenv("OPENAI_API_KEY", "sk-server-test")
    token = activate_no_env_fallback(disabled=True)
    try:
        with pytest.raises(DecisionConfigurationError, match="API key"):
            evaluate_decision(request, model=model)
    finally:
        reset_no_env_fallback(token)
    transport.assert_not_called()


def test_explicit_key_remains_usable_without_environment_fallback(execution, monkeypatch):
    request, model, transport = execution
    monkeypatch.setenv("OPENAI_API_KEY", "sk-server-test")
    token = activate_no_env_fallback(disabled=True)
    try:
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    finally:
        reset_no_env_fallback(token)
    assert transport.call_args.kwargs["api_key"] == "sk-explicit-test"


@pytest.mark.parametrize("variable", ["OPENAI_BASE_URL", "OPENAI_API_BASE", "LANGFLOW_OPENAI_API_BASE"])
def test_configured_custom_endpoint_is_not_silently_ignored(execution, monkeypatch, variable):
    request, model, transport = execution
    monkeypatch.setenv(variable, "https://custom.example/v1")
    with pytest.raises(DecisionConfigurationError, match="official hosted"):
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    transport.assert_not_called()


def test_no_env_fallback_ignores_legacy_endpoint_environment(execution, monkeypatch):
    request, model, transport = execution
    monkeypatch.setenv("OPENAI_API_BASE", "https://custom.example/v1")
    token = activate_no_env_fallback(disabled=True)
    try:
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    finally:
        reset_no_env_fallback(token)
    transport.assert_called_once()


@pytest.mark.parametrize("model", [[], [{}, {}], None, {"provider": "OpenAI"}])
def test_invalid_selection_fails_before_transport(execution, model):
    request, _, transport = execution
    with pytest.raises(DecisionConfigurationError):
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    transport.assert_not_called()


def test_generating_model_cannot_be_used_as_decision_model(execution):
    request, model, transport = execution
    model["name"] = "gpt-4o"
    with pytest.raises(DecisionConfigurationError, match="unavailable"):
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    transport.assert_not_called()


def test_disabled_model_and_capability_are_authoritative(execution, monkeypatch):
    request, model, transport = execution
    options = Mock(return_value=[])
    monkeypatch.setattr(unified_models, "get_decision_model_options", options)
    with pytest.raises(DecisionConfigurationError, match="disabled"):
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    options.return_value = [{**model, "metadata": {"capabilities": ["choice"]}}]
    with pytest.raises(DecisionConfigurationError, match="question kind"):
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    transport.assert_not_called()


def test_configuration_read_failure_does_not_invoke_provider(execution, monkeypatch):
    request, model, transport = execution
    monkeypatch.setattr(
        unified_models, "get_decision_model_options", Mock(side_effect=RuntimeError("database unavailable"))
    )
    with pytest.raises(RuntimeError, match="database unavailable"):
        evaluate_decision(request, model=model, api_key="sk-explicit-test")
    transport.assert_not_called()


@pytest.mark.parametrize("variable", ["OPENAI_API_KEY", "x-langflow-global-var-openai-api-key"])
def test_standalone_request_credentials_work_without_environment(execution, monkeypatch, variable):
    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    request, model, transport = execution
    service = VariableService()
    monkeypatch.setattr(credentials, "get_variable_service", lambda: service)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-wrong-process-key")
    token = activate_no_env_fallback(disabled=True)
    variables = activate_request_variables({variable: "sk-request-key"})
    try:
        evaluate_decision(request, model=model)
    finally:
        reset_request_variables(variables)
        reset_no_env_fallback(token)
    assert transport.call_args.kwargs["api_key"] == "sk-request-key"


def test_standalone_custom_credential_reference_uses_request_scope(execution, monkeypatch):
    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    request, model, transport = execution
    service = VariableService()
    monkeypatch.setattr(credentials, "get_variable_service", lambda: service)
    token = activate_no_env_fallback(disabled=True)
    variables = activate_request_variables({"MY_DECISION_KEY": "sk-custom-request-key"})
    try:
        evaluate_decision(request, model=model, api_key="MY_DECISION_KEY")
    finally:
        reset_request_variables(variables)
        reset_no_env_fallback(token)
    assert transport.call_args.kwargs["api_key"] == "sk-custom-request-key"


def test_standalone_request_endpoint_cannot_be_ignored(execution, monkeypatch):
    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    request, model, transport = execution
    service = VariableService()
    monkeypatch.setattr(credentials, "get_variable_service", lambda: service)
    token = activate_no_env_fallback(disabled=True)
    variables = activate_request_variables({"OPENAI_BASE_URL": "https://custom.example/v1"})
    try:
        with pytest.raises(DecisionConfigurationError, match="official hosted"):
            evaluate_decision(request, model=model, api_key="sk-explicit-test")
    finally:
        reset_request_variables(variables)
        reset_no_env_fallback(token)
    transport.assert_not_called()
