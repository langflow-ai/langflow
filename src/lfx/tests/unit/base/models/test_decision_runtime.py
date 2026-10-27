"""Decision execution rejects denied/configuration-invalid requests before inference."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.base.models import unified_models
from lfx.base.models.decisions import providers
from lfx.base.models.decisions.runtime import decision_token_usage, evaluate_decision
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest, DecisionResult
from lfx.schema.properties import Usage
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
from pydantic import SecretStr


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
    monkeypatch.setenv("OPENAI_API_KEY", "sk-explicit-test")
    return request, model, transport


def test_provider_key_uses_canonical_metadata_and_typed_policy(execution):
    request, model, transport = execution
    model["metadata"] = {"model_type": "llm", "base_url": "https://attacker.invalid", "capabilities": []}
    result = evaluate_decision(request, model=[model])
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
        evaluate_decision(request, model=model)
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


@pytest.mark.parametrize("variable", ["OPENAI_BASE_URL", "OPENAI_API_BASE", "LANGFLOW_OPENAI_API_BASE"])
def test_configured_custom_endpoint_is_not_silently_ignored(execution, monkeypatch, variable):
    request, model, transport = execution
    monkeypatch.setenv(variable, "https://custom.example/v1")
    with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
        evaluate_decision(request, model=model)
    transport.assert_not_called()


def test_no_env_fallback_ignores_legacy_endpoint_environment(execution, monkeypatch):
    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    request, model, transport = execution
    monkeypatch.setattr(credentials, "get_variable_service", lambda: VariableService())
    monkeypatch.setenv("OPENAI_API_BASE", "https://custom.example/v1")
    token = activate_no_env_fallback(disabled=True)
    variables = activate_request_variables({"OPENAI_API_KEY": "sk-request-key"})
    try:
        evaluate_decision(request, model=model)
    finally:
        reset_request_variables(variables)
        reset_no_env_fallback(token)
    transport.assert_called_once()


@pytest.mark.parametrize("model", [[], [{}, {}], None, {"provider": "OpenAI"}])
def test_invalid_selection_fails_before_transport(execution, model):
    request, _, transport = execution
    with pytest.raises(DecisionConfigurationError):
        evaluate_decision(request, model=model)
    transport.assert_not_called()


def test_generating_model_cannot_be_used_as_decision_model(execution):
    request, model, transport = execution
    model["name"] = "gpt-4o"
    with pytest.raises(DecisionConfigurationError, match="no longer offered"):
        evaluate_decision(request, model=model)
    transport.assert_not_called()


def test_switched_off_model_still_runs_like_a_language_model(execution, monkeypatch):
    """Model Providers' switches shape the picker only, so lfx run and serve, which have none, can run any model."""
    from lfx.base.models.unified_models import model_catalog

    async def switched_off(*_args, **_kwargs):
        return {"gpt-6-luna"}, set()

    request, model, transport = execution
    monkeypatch.setattr(model_catalog, "_get_model_status", switched_off)
    variables = activate_request_variables({"OPENAI_API_KEY": "sk-request-key"})
    try:
        evaluate_decision(request, model=model, user_id="00000000-0000-0000-0000-000000000001")
    finally:
        reset_request_variables(variables)
    transport.assert_called_once()


def test_unoffered_model_and_capability_are_authoritative(execution, monkeypatch):
    request, model, transport = execution
    options = Mock(return_value=[])
    monkeypatch.setattr(unified_models, "get_decision_model_options", options)
    with pytest.raises(DecisionConfigurationError, match="no longer offered"):
        evaluate_decision(request, model=model)
    options.return_value = [{**model, "metadata": {"capabilities": ["choice"]}}]
    with pytest.raises(DecisionConfigurationError, match="Decision Type"):
        evaluate_decision(request, model=model)
    transport.assert_not_called()


def test_configuration_read_failure_does_not_invoke_provider(execution, monkeypatch):
    request, model, transport = execution
    monkeypatch.setattr(
        unified_models, "get_decision_model_options", Mock(side_effect=RuntimeError("database unavailable"))
    )
    with pytest.raises(RuntimeError, match="database unavailable"):
        evaluate_decision(request, model=model)
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


def test_standalone_request_endpoint_cannot_be_ignored(execution, monkeypatch):
    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    request, model, transport = execution
    service = VariableService()
    monkeypatch.setattr(credentials, "get_variable_service", lambda: service)
    token = activate_no_env_fallback(disabled=True)
    variables = activate_request_variables({"OPENAI_BASE_URL": "https://custom.example/v1"})
    try:
        with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
            evaluate_decision(request, model=model)
    finally:
        reset_request_variables(variables)
        reset_no_env_fallback(token)
    transport.assert_not_called()


def test_callers_per_request_key_for_its_own_provider_comes_first(execution):
    request, model, transport = execution
    evaluate_decision(request, model=model, request_variables={"OPENAI_API_KEY": "sk-header-key"})
    assert transport.call_args.kwargs["api_key"] == "sk-header-key"


@pytest.fixture
def saved_provider_variables(monkeypatch):
    from lfx.base.models.unified_models import credentials

    @asynccontextmanager
    async def session_scope():
        yield object()

    async def read_variable(*, name, **_kwargs):
        if name == "OPENAI_API_KEY":
            msg = "Saved API key cannot be decrypted"
            raise ValueError(msg)
        return SecretStr("https://api.openai.com/v1")

    service = Mock(get_variable=AsyncMock(side_effect=read_variable))
    monkeypatch.setattr(credentials, "session_scope", session_scope)
    monkeypatch.setattr(credentials, "get_variable_service", lambda: service)
    return service


@pytest.mark.parametrize("alias", ["OPENAI_API_KEY", "x-langflow-global-var-openai-api-key"])
def test_request_key_skips_broken_saved_secret(execution, saved_provider_variables, alias):
    request, model, transport = execution
    token = activate_no_env_fallback(disabled=True)
    try:
        evaluate_decision(
            request,
            model=model,
            user_id="00000000-0000-0000-0000-000000000001",
            request_variables={alias: SecretStr("sk-request-key")},
        )
    finally:
        reset_no_env_fallback(token)
    assert transport.call_args.kwargs["api_key"] == "sk-request-key"
    names = [call.kwargs["name"] for call in saved_provider_variables.get_variable.await_args_list]
    assert names == ["OPENAI_BASE_URL"]


@pytest.mark.parametrize("request_variables", [None, {}, {"OPENAI_API_KEY": "   "}])
def test_missing_request_override_does_not_hide_broken_saved_secret(
    execution, saved_provider_variables, request_variables
):
    request, model, transport = execution
    with pytest.raises(ValueError, match="cannot be decrypted"):
        evaluate_decision(
            request,
            model=model,
            user_id="00000000-0000-0000-0000-000000000001",
            request_variables=request_variables,
        )
    transport.assert_not_called()
    saved_provider_variables.get_variable.assert_awaited_once()


@pytest.mark.parametrize("broken_setting", [False, True])
def test_request_key_still_reads_saved_credential_endpoint(execution, saved_provider_variables, broken_setting):
    request, model, transport = execution
    saved_provider_variables.get_variable.side_effect = (
        ValueError("Saved endpoint cannot be decrypted") if broken_setting else None
    )
    saved_provider_variables.get_variable.return_value = SecretStr("https://custom.example/v1")
    expected_error = ValueError if broken_setting else DecisionConfigurationError
    expected_message = "cannot be decrypted" if broken_setting else "official OpenAI endpoint"
    with pytest.raises(expected_error, match=expected_message):
        evaluate_decision(
            request,
            model=model,
            user_id="00000000-0000-0000-0000-000000000001",
            request_variables={"OPENAI_API_KEY": "sk-request-key"},
        )
    transport.assert_not_called()


@pytest.mark.parametrize("variable", ["OPENAI_BASE_URL", "OPENAI_API_BASE"])
def test_callers_per_request_endpoint_cannot_be_ignored(execution, variable):
    request, model, transport = execution
    request_variables = {variable: "https://proxy.example/v1", "OPENAI_API_KEY": "sk-proxy-key"}
    with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
        evaluate_decision(request, model=model, request_variables=request_variables)
    transport.assert_not_called()


@pytest.mark.parametrize("masking_value", ["", " ", "https://api.openai.com/v1", None])
@pytest.mark.parametrize("variable", ["OPENAI_BASE_URL", "OPENAI_API_BASE"])
def test_per_request_value_cannot_hide_a_configured_proxy(execution, monkeypatch, variable, masking_value):
    request, model, transport = execution
    monkeypatch.setenv(variable, "https://proxy.example/v1")
    with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
        evaluate_decision(request, model=model, request_variables={variable: masking_value})
    transport.assert_not_called()


@pytest.mark.parametrize(
    "variable",
    [
        "x-langflow-global-var-openai-api-base",
        "x-langflow-global-var-openai-base-url",
        # X-LANGFLOW-GLOBAL-VAR-OPENAI-BASE-URL as header extraction leaves it.
        "OPENAI-BASE-URL",
        "OPENAI-API-BASE",
    ],
)
def test_aliased_per_request_endpoint_cannot_be_ignored(execution, variable):
    request, model, transport = execution
    request_variables = {variable: "https://proxy.example/v1", "x-langflow-global-var-openai-api-key": "sk-proxy-key"}
    with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
        evaluate_decision(request, model=model, request_variables=request_variables)
    transport.assert_not_called()


def test_a_proxy_endpoint_in_the_request_variables_json_cannot_be_ignored(execution, monkeypatch):
    """With no request scope, lfx reads the LANGFLOW_REQUEST_VARIABLES JSON for the key, so the guard reads it too."""
    import json

    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    request, model, transport = execution
    monkeypatch.setattr(credentials, "get_variable_service", lambda: VariableService())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv(
        "LANGFLOW_REQUEST_VARIABLES",
        json.dumps({"OPENAI_API_KEY": "sk-proxy-key", "OPENAI_API_BASE": "https://proxy.example/v1"}),
    )
    with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
        evaluate_decision(request, model=model)
    transport.assert_not_called()


def test_aliased_endpoint_in_the_serve_request_scope_cannot_be_ignored(execution, monkeypatch):
    """Lfx serve keeps x-langflow-global-var-* names and resolves the proxy key through them."""
    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    request, model, transport = execution
    monkeypatch.setattr(credentials, "get_variable_service", lambda: VariableService())
    token = activate_no_env_fallback(disabled=True)
    variables = activate_request_variables(
        {
            "x-langflow-global-var-openai-api-base": "https://proxy.example/v1",
            "x-langflow-global-var-openai-api-key": "sk-proxy-key",
        }
    )
    try:
        with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
            evaluate_decision(request, model=model)
    finally:
        reset_request_variables(variables)
        reset_no_env_fallback(token)
    transport.assert_not_called()


@pytest.mark.parametrize("name", ["OPENAI-API-KEY", "x-langflow-global-var-openai-api-key"])
def test_callers_key_in_any_request_form_beats_the_ambient_key(execution, name):
    request, model, transport = execution  # the fixture leaves an ambient OPENAI_API_KEY set
    evaluate_decision(request, model=model, request_variables={name: "sk-caller-key"})
    assert transport.call_args.kwargs["api_key"] == "sk-caller-key"


def test_prefixed_environment_key_is_used(execution, monkeypatch):
    request, model, transport = execution
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setenv("LANGFLOW_OPENAI_API_KEY", "sk-prefixed-test")
    evaluate_decision(request, model=model)
    assert transport.call_args.kwargs["api_key"] == "sk-prefixed-test"


def test_per_request_keys_for_other_providers_are_ignored(execution):
    request, model, transport = execution
    evaluate_decision(request, model=model, request_variables={"ANTHROPIC_API_KEY": "sk-ant-other"})
    assert transport.call_args.kwargs["api_key"] == "sk-explicit-test"


def _with_usage(usage):
    return DecisionResult(kind="boolean", provider="TypeSafe", model="jev-1.13.0", probability_true=0.9, usage=usage)


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (
            {"input_tokens": 296, "output_tokens": 0, "total_tokens": 296},
            Usage(input_tokens=296, output_tokens=0, total_tokens=296),
        ),
        # A provider that leaves out the total gets one summed from the counts it sent.
        ({"input_tokens": 40, "output_tokens": 2}, Usage(input_tokens=40, output_tokens=2, total_tokens=42)),
        ({"output_tokens": 3}, Usage(input_tokens=None, output_tokens=3, total_tokens=3)),
        # Details Langflow doesn't show are left on the evidence.
        (
            {"input_tokens": 10, "output_tokens": 1, "input_tokens_details": {"cached_tokens": 8}},
            Usage(input_tokens=10, output_tokens=1, total_tokens=11),
        ),
    ],
)
def test_decision_token_usage_reads_the_providers_counts(usage, expected):
    assert decision_token_usage(_with_usage(usage)) == expected


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"total_tokens": 12},
        # Not counts: a result built outside parse_response is never trusted to hold them.
        {"input_tokens": -1, "output_tokens": "2"},
        {"input_tokens": True, "output_tokens": 1.5},
    ],
)
def test_decision_token_usage_is_none_without_counts(usage):
    assert decision_token_usage(_with_usage(usage)) is None
