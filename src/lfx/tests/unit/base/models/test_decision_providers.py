"""Documented provider fixtures exercise wire translation without paid inference."""

import copy
import json

import httpx
import pytest
from lfx.base.models.decision_constants import DECISION_MODELS_DETAILED
from lfx.base.models.decisions import providers
from lfx.base.models.decisions.schema import (
    DecisionConfigurationError,
    DecisionEvaluationError,
    DecisionOption,
    DecisionRequest,
)
from lfx.base.models.unified_models import get_provider_secret_variable_key

PROVIDERS = tuple(providers.ENDPOINTS)
# Each provider's first catalog row, the model its key is checked with by default.
DEFAULT_MODELS = {row["provider"]: row["name"] for row in reversed(DECISION_MODELS_DETAILED)}


def request_for(kind):
    candidates = (DecisionOption(id="a", label="Low"), DecisionOption(id="b", label="High"))
    return DecisionRequest(
        kind=kind,
        question="Which level applies?",
        context={"text": "Example"},
        options=candidates if kind == "choice" else (),
        levels=candidates if kind == "score" else (),
    )


def response_for(provider, kind):
    if kind == "boolean":
        answer = {"type": "predicate", "probability": 0.7} if provider == "OpenAI" else {"type": "noul", "noul": 0.7}
    else:
        answer = {"type": kind, "confidence": 0.25}
        if provider == "OpenAI":
            answer["probabilities"] = (
                [{"value": "a", "probability": 0.3}, {"value": "b", "probability": 0.7}]
                if kind == "choice"
                else [{"value": 0, "label": "a", "probability": 0.3}, {"value": 1, "label": "b", "probability": 0.7}]
            )
        else:
            answer["probabilities"] = {"a": 0.3, "b": 0.7} if kind == "choice" else {"0": 0.3, "1": 0.7}
            if kind == "score":
                answer["legend"] = {"0": "Low", "1": "High"}
        answer["choice" if kind == "choice" else "score"] = "b" if kind == "choice" else 0.7
    if provider == "OpenAI":
        answer["name"] = "decision"
    return {
        "model": DEFAULT_MODELS[provider],
        "answers": [answer] if provider == "OpenAI" else {"decision": answer},
    }


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("kind", ["choice", "boolean", "score"])
def test_wire_contract(provider, kind):
    request = request_for(kind)
    payload = providers.build_payload(provider, DEFAULT_MODELS[provider], request)
    if provider == "OpenAI":
        question = payload["questions"][0]
        assert payload["input"] == '{"text": "Example"}'
        assert question["name"] == "decision"
        if kind == "choice":
            assert question["choices"][0] == {"value": "a", "description": "Low"}
        elif kind == "score":
            assert question["levels"][0] == {"label": "a", "description": "Low"}
    else:
        question = payload["questions"]["decision"]
        assert payload["state"] == {"text": "Example"}
        if kind == "choice":
            assert question["criteria"] == {"a": "Low", "b": "High"}
        elif kind == "score":
            assert question["criteria"] == ["Low", "High"]
    result = providers.parse_response(provider, request, response_for(provider, kind))
    if kind == "boolean":
        assert result.probability_true == 0.7
        assert result.confidence is None
    else:
        assert result.probabilities == {"a": 0.3, "b": 0.7}
        assert result.confidence == 0.25
    assert result.model_source == ("request" if provider == "Perplexity" else "response")


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    "mutation", ["missing", "unknown", "nan", "negative", "sum", "duplicate", "mismatch", "chosen"]
)
def test_malformed_choice_never_becomes_uncertainty(provider, mutation):
    body = response_for(provider, "choice")
    answer = body["answers"][0] if provider == "OpenAI" else body["answers"]["decision"]
    if mutation == "missing":
        del answer["probabilities"]
    elif mutation == "mismatch":
        answer["type"] = "score"
    elif mutation == "chosen":
        answer["choice"] = "a"
    elif provider == "OpenAI":
        if mutation == "unknown":
            answer["probabilities"][0]["value"] = "secret"
        elif mutation == "duplicate":
            answer["probabilities"].append(copy.deepcopy(answer["probabilities"][0]))
        else:
            answer["probabilities"][0]["probability"] = {"nan": float("nan"), "negative": -1, "sum": 0.9}[mutation]
    elif mutation in {"unknown", "duplicate"}:
        answer["probabilities"]["secret"] = answer["probabilities"].pop("a")
    else:
        answer["probabilities"]["a"] = {"nan": float("nan"), "negative": -1, "sum": 0.9}[mutation]
    with pytest.raises(DecisionEvaluationError, match="couldn't use") as error:
        providers.parse_response(provider, request_for("choice"), body)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_hosted_score_level_limit(provider):
    request = DecisionRequest(
        kind="score",
        context="text",
        question="rate",
        levels=tuple(DecisionOption(id=str(i), label=f"Level {i}") for i in range(11)),
    )
    with pytest.raises(DecisionConfigurationError, match="10 Score levels"):
        providers.build_payload(provider, DEFAULT_MODELS[provider], request)


def test_refusal_is_not_false():
    result = providers.parse_response(
        "OpenAI",
        request_for("boolean"),
        {
            "model": "gpt-6-luna",
            "answers": [{"type": "refusal", "name": "decision"}],
        },
    )
    assert result.status == "refusal"
    assert result.refusal is None  # no reason given, none invented
    assert result.probability_true is None
    assert result.probabilities is None


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (302, DecisionEvaluationError),
        (401, PermissionError),
        (403, PermissionError),
        (400, DecisionConfigurationError),
        (429, DecisionEvaluationError),
        (500, DecisionEvaluationError),
    ],
)
def test_transport_errors_redacted_and_never_follow_redirects(monkeypatch, status, error):
    def post(url, **kwargs):
        assert url == providers.ENDPOINTS["OpenAI"]
        assert kwargs["follow_redirects"] is False
        assert kwargs["headers"]["Authorization"] == "Bearer private-token"
        return httpx.Response(status, text="private-token private user content")

    monkeypatch.setattr(providers, "provider_safe_httpx_post", post)
    with pytest.raises(error) as caught:
        providers.evaluate_provider("OpenAI", "gpt-6-luna", request_for("choice"), api_key="private-token")
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("secret"), httpx.ConnectError("secret")])
def test_transport_exceptions_redacted(monkeypatch, failure):
    def post(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(providers, "provider_safe_httpx_post", post)
    with pytest.raises(DecisionEvaluationError) as caught:
        providers.evaluate_provider("OpenAI", "gpt-6-luna", request_for("boolean"), api_key="key")
    assert "secret" not in str(caught.value)


def test_validator_never_uses_environment_or_custom_host(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "server-token")
    with pytest.raises(ValueError, match="Enter the OpenAI API key"):
        providers.validate_decision_provider_key("OpenAI", {}, "gpt-6-luna")
    with pytest.raises(ValueError, match="official OpenAI endpoint"):
        providers.validate_decision_provider_key(
            "OpenAI", {"OPENAI_API_KEY": "key", "OPENAI_BASE_URL": "https://other.example"}, "gpt-6-luna"
        )


def test_usage_only_emits_documented_token_counts():
    body = response_for("OpenAI", "boolean")
    body["usage"] = {
        "input_tokens": 10,
        "output_tokens": 0,
        "secret": "private-token",
        "input_tokens_details": {"cached_tokens": 3, "secret": "private-token"},
    }
    result = providers.parse_response("OpenAI", request_for("boolean"), body)
    assert result.usage == {"input_tokens": 10, "output_tokens": 0, "input_tokens_details": {"cached_tokens": 3}}


def test_openai_score_rejects_wrong_index():
    body = response_for("OpenAI", "score")
    body["answers"][0]["probabilities"][1]["value"] = 0
    with pytest.raises(DecisionEvaluationError, match="couldn't use"):
        providers.parse_response("OpenAI", request_for("score"), body)


def test_perplexity_documented_score_fixture():
    request = DecisionRequest(
        kind="score",
        question="Severity?",
        context="damaged",
        levels=tuple(
            DecisionOption(id=str(i), label=label)
            for i, label in enumerate(["Cosmetic", "Inconvenient", "Product unusable"])
        ),
    )
    result = providers.parse_response(
        "Perplexity",
        request,
        {
            "model": "pplx-decider-latest",
            "answers": {
                "decision": {
                    "type": "score",
                    "score": 1.7838686319784252,
                    "confidence": 0.7838686319784252,
                    "legend": {"0": "Cosmetic", "1": "Inconvenient", "2": "Product unusable"},
                    "probabilities": {"0": 0.008423954913615923, "1": 0.199283458194343, "2": 0.7922925868920411},
                }
            },
            "usage": {"input_tokens": 367, "output_tokens": 3},
        },
    )
    assert result.score == 1.7838686319784252


@pytest.mark.parametrize("provider", ["TypeSafe", "Perplexity"])
def test_duplicate_wire_keys_rejected_before_json_collapses_them(provider, monkeypatch):
    def post(*_args, **_kwargs):
        return httpx.Response(
            200,
            content=b'{"model":"model","answers":{"decision":{"type":"choice",'
            b'"choice":"b","confidence":0.25,"probabilities":{"a":0.1,"a":0.3,"b":0.7}}}}',
        )

    monkeypatch.setattr(providers, "provider_safe_httpx_post", post)
    with pytest.raises(DecisionEvaluationError, match="couldn't read"):
        providers.evaluate_provider(provider, DEFAULT_MODELS[provider], request_for("choice"), api_key="key")


@pytest.mark.parametrize("provider", ["TypeSafe", "Perplexity"])
def test_score_legend_must_preserve_requested_order(provider):
    body = response_for(provider, "score")
    body["answers"]["decision"]["legend"] = {"0": "High", "1": "Low"}
    with pytest.raises(DecisionEvaluationError, match="couldn't use"):
        providers.parse_response(provider, request_for("score"), body)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_choice_option_limit(provider):
    request = DecisionRequest(
        kind="choice",
        context="text",
        question="Choose",
        options=tuple(DecisionOption(id=str(i), label=f"Option {i}") for i in range(256)),
    )
    with pytest.raises(DecisionConfigurationError, match="255 options"):
        providers.build_payload(provider, DEFAULT_MODELS[provider], request)


@pytest.mark.parametrize("timeout", [0, -1, 301, float("nan"), float("inf")])
def test_invalid_timeout_fails_before_transport(timeout):
    with pytest.raises(DecisionConfigurationError, match="Timeout"):
        providers.evaluate_provider("OpenAI", "gpt-6-luna", request_for("boolean"), api_key="key", timeout=timeout)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_credential_validation_uses_explicit_key_and_boolean_request(provider, monkeypatch):
    calls = []
    monkeypatch.setenv(get_provider_secret_variable_key(provider), "server-secret")
    monkeypatch.setattr(providers, "evaluate_provider", lambda *args, **kwargs: calls.append((args, kwargs)))
    providers.validate_decision_provider_key(
        provider, {get_provider_secret_variable_key(provider): "tenant-key"}, DEFAULT_MODELS[provider]
    )
    args, kwargs = calls.pop()
    assert args[0] == provider
    assert args[1] == DEFAULT_MODELS[provider]
    assert args[2].kind == "boolean"
    assert kwargs == {"api_key": "tenant-key", "timeout": 15}


def test_key_check_defaults_to_an_allowed_decision_model(monkeypatch):
    """Blocking a provider's first decision model does not stop its key being checked with another."""
    from lfx.base.models.unified_models import validate_model_provider_key
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicyPurpose,
        ModelProviderPolicySnapshot,
    )

    policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"perplexity"}),
        allowed_provider_ids=frozenset({"perplexity"}),
        blocked_model_keys=frozenset({"perplexity::decision::pplx-decider-latest"}),
    )
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy)
    checked = []
    monkeypatch.setattr(providers, "validate_decision_provider_key", lambda *args: checked.append(args))
    validate_model_provider_key("Perplexity", {"PERPLEXITY_API_KEY": "tenant-key"})
    assert checked == [("Perplexity", {"PERPLEXITY_API_KEY": "tenant-key"}, "pplx-decider-flash-latest")]


def test_key_check_never_runs_a_chat_model_that_policy_blocks(monkeypatch):
    """A check runs a real model, so a named or default chat model needs model-level permission."""
    from lfx.base.models.unified_models import get_unified_models_detailed, validate_model_provider_key
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicyError,
        ModelProviderPolicyPurpose,
        ModelProviderPolicySnapshot,
    )

    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    rows = get_unified_models_detailed(providers=["OpenAI"], model_type="llm")[0]["models"]
    blocked, allowed = rows[0]["model_name"], rows[1]["model_name"]
    policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"openai"}),
        allowed_provider_ids=frozenset({"openai"}),
        blocked_model_keys=frozenset({f"openai::llm::{blocked}"}),
    )
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy)
    ran = []

    class Chat:
        def __init__(self, **kwargs):
            ran.append(kwargs["model_name"])

        def invoke(self, _prompt):
            return "ok"

    import sys
    import types

    # langchain_openai may not be installed here; the check only needs its ChatOpenAI.
    monkeypatch.setitem(sys.modules, "langchain_openai", types.SimpleNamespace(ChatOpenAI=Chat))
    with pytest.raises(ModelProviderPolicyError):
        validate_model_provider_key("OpenAI", {"OPENAI_API_KEY": "tenant-key"}, blocked, model_type="llm")
    assert ran == []
    validate_model_provider_key("OpenAI", {"OPENAI_API_KEY": "tenant-key"})
    assert ran == [allowed]
    # Naming the blocked chat model as another kind doesn't run it as a chat call.
    ran.clear()
    validate_model_provider_key("OpenAI", {"OPENAI_API_KEY": "tenant-key"}, blocked, model_type="embeddings")
    assert ran == [allowed]


@pytest.mark.parametrize("provider", ["typesafe", "TypeSafe"])
@pytest.mark.parametrize("model_type", [None, "decision"])
def test_key_validation_treats_provider_ids_like_display_names(monkeypatch, provider, model_type):
    from lfx.base.models.unified_models import validate_model_provider_key
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicyPurpose,
        ModelProviderPolicySnapshot,
    )

    policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"typesafe"}),
        allowed_provider_ids=frozenset({"typesafe"}),
    )
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy)
    checked = []
    monkeypatch.setattr(providers, "validate_decision_provider_key", lambda *args: checked.append(args))
    validate_model_provider_key(provider, {"TYPESAFE_API_KEY": "tenant-key"}, model_type=model_type)
    assert checked == [("TypeSafe", {"TYPESAFE_API_KEY": "tenant-key"}, "jev-latest")]


def test_dns_failure_is_operational_but_ssrf_block_always_stops(monkeypatch):
    import socket

    from lfx.utils.ssrf_protection import SSRFProtectionError

    def dns_failure(*_args, **_kwargs):
        msg = "DNS resolution failed for secret.internal"
        raise SSRFProtectionError(msg) from socket.gaierror("nodename nor servname provided")

    def blocked(*_args, **_kwargs):
        msg = "Access to private IP 10.0.0.5 for secret.internal is blocked"
        raise SSRFProtectionError(msg)

    monkeypatch.setattr(providers, "provider_safe_httpx_post", dns_failure)
    with pytest.raises(DecisionEvaluationError) as caught:
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("choice"), api_key="key")
    assert caught.value.category == "transport"
    assert "secret" not in str(caught.value)

    monkeypatch.setattr(providers, "provider_safe_httpx_post", blocked)
    with pytest.raises(DecisionConfigurationError, match="network security settings block") as caught:
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("choice"), api_key="key")
    assert "secret" not in str(caught.value)
    assert "10.0.0.5" not in str(caught.value)


# OpenAI reports an exhausted account as 429 insufficient_quota, not 402.
@pytest.mark.parametrize("status", [402, 429])
def test_unpaid_account_stops_and_reports_only_a_safe_error_code(monkeypatch, status):
    body = '{"error": {"code": "insufficient_quota", "message": "private user content"}}'
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *_a, **_k: httpx.Response(status, text=body))
    with pytest.raises(PermissionError, match=rf"billing or credit \(HTTP {status}, insufficient_quota\)") as caught:
        providers.evaluate_provider("OpenAI", "gpt-6-luna", request_for("choice"), api_key="key")
    assert "private" not in str(caught.value)


def test_unsafe_provider_error_code_is_dropped(monkeypatch):
    body = '{"error": {"code": "has spaces and private user content"}}'
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *_a, **_k: httpx.Response(500, text=body))
    with pytest.raises(DecisionEvaluationError) as caught:
        providers.evaluate_provider("OpenAI", "gpt-6-luna", request_for("choice"), api_key="key")
    assert str(caught.value) == "OpenAI had a server problem (HTTP 500). Try again later."


@pytest.mark.parametrize("provider", PROVIDERS)
def test_choice_without_optional_evidence_is_still_valid(provider):
    payload = response_for(provider, "choice")
    answer = payload["answers"][0] if provider == "OpenAI" else payload["answers"]["decision"]
    del answer["confidence"]
    del answer["choice"]
    result = providers.parse_response(provider, request_for("choice"), payload)
    assert result.probabilities == {"a": 0.3, "b": 0.7}
    assert result.confidence is None
    assert result.selected_option is None


def test_boolean_keeps_supplied_confidence_separate_from_probability():
    payload = response_for("OpenAI", "boolean")
    payload["answers"][0]["confidence"] = 0.4
    result = providers.parse_response("OpenAI", request_for("boolean"), payload)
    assert (result.probability_true, result.confidence) == (0.7, 0.4)


def test_openai_refusal_keeps_provider_reason():
    result = providers.parse_response(
        "OpenAI",
        request_for("choice"),
        {"model": "gpt-6-luna", "answers": [{"type": "refusal", "name": "decision", "refusal": "Policy reason"}]},
    )
    assert (result.status, result.refusal) == ("refusal", "Policy reason")


@pytest.mark.parametrize("provider", ["TypeSafe", "Perplexity"])
def test_undocumented_refusal_type_is_invalid_not_refusal(provider):
    payload = response_for(provider, "choice")
    payload["answers"]["decision"] = {"type": "refusal", "refusal": "declined"}
    with pytest.raises(DecisionEvaluationError, match="couldn't use"):
        providers.parse_response(provider, request_for("choice"), payload)


@pytest.mark.parametrize(
    ("status", "body"),
    [(413, "too large"), (400, '{"error": {"code": "max_tokens_exceeded", "message": "private user content"}}')],
)
def test_oversized_input_is_operational_not_configuration(monkeypatch, status, body):
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *_a, **_k: httpx.Response(status, text=body))
    with pytest.raises(DecisionEvaluationError) as caught:
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("choice"), api_key="key")
    assert caught.value.category == "input_too_large"
    assert "private" not in str(caught.value)


@pytest.mark.parametrize(
    ("mutate", "cause"),
    [
        (lambda answer: answer.update(probabilities={"a": 0.3, "b": 0.5}), "sum to one"),
        (lambda answer: answer.update(probabilities={"a": 0.3, "z": 0.7}), "requested candidate IDs"),
        (lambda answer: answer.pop("probabilities"), "missing field 'probabilities'"),
        (lambda answer: answer.update(type="score"), "does not match"),
    ],
)
def test_invalid_response_names_its_cause_without_provider_content(mutate, cause):
    payload = response_for("TypeSafe", "choice")
    mutate(payload["answers"]["decision"])
    payload["answers"]["decision"]["note"] = "private user content"
    with pytest.raises(DecisionEvaluationError, match="couldn't use") as caught:
        providers.parse_response("TypeSafe", request_for("choice"), payload)
    assert cause in str(caught.value)
    assert caught.value.category == "invalid_response"
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("variable", ["OPENAI_API_BASE", "OPENAI_BASE_URL", "LANGFLOW_OPENAI_BASE_URL"])
def test_key_check_refuses_a_proxy_base_url_from_the_environment(monkeypatch, variable):
    """A key meant for an OpenAI-compatible proxy is never posted to the official endpoint."""
    monkeypatch.setenv(variable, "https://proxy.example/v1")
    sent = []
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *args, **_kwargs: sent.append(args))
    with pytest.raises(ValueError, match="official OpenAI endpoint"):
        providers.validate_decision_provider_key("OpenAI", {"OPENAI_API_KEY": "proxy-key"}, "gpt-6-luna")
    assert not sent


def test_unexpected_answer_type_is_not_echoed():
    payload = response_for("TypeSafe", "choice")
    payload["answers"]["decision"]["type"] = "private provider text"
    with pytest.raises(DecisionEvaluationError, match="does not match") as caught:
        providers.parse_response("TypeSafe", request_for("choice"), payload)
    assert "private" not in str(caught.value)


def test_provider_chosen_probability_key_is_not_echoed():
    payload = response_for("TypeSafe", "choice")
    payload["answers"]["decision"]["probabilities"] = {"a": 0.3, "private provider key": 1.5}
    with pytest.raises(DecisionEvaluationError, match="couldn't use") as caught:
        providers.parse_response("TypeSafe", request_for("choice"), payload)
    assert "probabilities" in str(caught.value)
    assert "private" not in str(caught.value)


def test_overlong_model_name_is_an_invalid_response():
    payload = response_for("TypeSafe", "choice")
    payload["model"] = "m" * 129
    with pytest.raises(DecisionEvaluationError, match="couldn't use") as caught:
        providers.parse_response("TypeSafe", request_for("choice"), payload)
    assert "m" * 129 not in str(caught.value)


@pytest.mark.parametrize("provider", ["TypeSafe", "Perplexity"])
@pytest.mark.parametrize(
    ("yes", "no", "criteria"),
    [
        ("Asks for money back", "Anything else", {"true": "Asks for money back", "false": "Anything else"}),
        ("Asks for money back", "", {"true": "Asks for money back"}),
        ("", "", None),
    ],
)
def test_boolean_sends_what_yes_and_no_mean(provider, yes, no, criteria):
    request = DecisionRequest(kind="boolean", question="Refund?", context="x", yes_description=yes, no_description=no)
    question = providers.build_payload(provider, DEFAULT_MODELS[provider], request)["questions"]["decision"]
    assert question.get("criteria") == criteria


def test_openai_refuses_yes_and_no_descriptions_instead_of_dropping_them():
    request = DecisionRequest(kind="boolean", question="Refund?", context="x", yes_description="Money back")
    with pytest.raises(DecisionConfigurationError, match="take no descriptions of what Yes and No mean"):
        providers.build_payload("OpenAI", "gpt-6-luna", request)


def test_a_blank_yes_or_no_description_is_none():
    request = DecisionRequest(kind="boolean", question="Refund?", context="x", yes_description="  ", no_description="")
    assert "criteria" not in providers.build_payload("TypeSafe", "jev-latest", request)["questions"]["decision"]
    assert providers.build_payload("OpenAI", "gpt-6-luna", request)["questions"][0]["type"] == "predicate"


@pytest.mark.parametrize(("header", "expected"), [("req_5f0c9a", "req_5f0c9a"), ("has spaces <b>", None), (None, None)])
def test_result_keeps_only_a_safe_request_id(monkeypatch, header, expected):
    headers = {"x-request-id": header} if header else {}
    response = httpx.Response(200, json=response_for("Perplexity", "boolean"), headers=headers)
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *_a, **_k: response)
    result = providers.evaluate_provider("Perplexity", "pplx-decider-latest", request_for("boolean"), api_key="key")
    assert result.request_id == expected


def test_undecodable_answers_name_the_providers_request_id(monkeypatch):
    response = httpx.Response(200, content=b'{"model": "a", "model": "b"}', headers={"x-request-id": "req_5f0c9a"})
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *_a, **_k: response)
    with pytest.raises(DecisionEvaluationError, match=r"couldn't read \(request ID req_5f0c9a\)\."):
        providers.evaluate_provider("Perplexity", "pplx-decider-latest", request_for("choice"), api_key="key")


def test_failures_name_the_providers_request_id(monkeypatch):
    response = httpx.Response(503, text="private user content", headers={"x-request-id": "req_5f0c9a"})
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *_a, **_k: response)
    with pytest.raises(DecisionEvaluationError) as caught:
        providers.evaluate_provider("Perplexity", "pplx-decider-latest", request_for("choice"), api_key="key")
    assert str(caught.value) == "Perplexity had a server problem (HTTP 503, request ID req_5f0c9a). Try again later."


@pytest.mark.parametrize(
    ("status", "error", "says"),
    [
        (401, PermissionError, "didn't accept the API key"),
        (402, PermissionError, "billing or credit"),
        (403, PermissionError, "can't use decision models"),
        (404, DecisionConfigurationError, "doesn't offer this decision model"),
        (400, DecisionConfigurationError, "couldn't accept this decision request"),
        (429, DecisionEvaluationError, "rate-limiting this API key"),
        (503, DecisionEvaluationError, "server problem"),
    ],
)
def test_each_failure_says_what_to_do(monkeypatch, status, error, says):
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *_a, **_k: httpx.Response(status, text="{}"))
    with pytest.raises(error, match=says) as caught:
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("choice"), api_key="key")
    assert f"(HTTP {status})" in str(caught.value)


@pytest.mark.parametrize(
    ("provider", "model_type"), [("OpenAI", "decision"), ("TypeSafe", None), ("Perplexity", "llm")]
)
def test_a_key_check_only_runs_catalogued_decision_models(monkeypatch, provider, model_type):
    from lfx.base.models.unified_models import validate_model_provider_key

    sent = []
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda url, **_kwargs: sent.append(url))
    with pytest.raises(ValueError, match="has no decision model by that name"):
        validate_model_provider_key(provider, {f"{provider.upper()}_API_KEY": "key"}, "gpt-4o", model_type=model_type)
    assert sent == []


def test_decision_models_start_on():
    """Decision models start on by the language-model rule, each provider's first five, OpenAI's too."""
    from lfx.base.models.unified_models import get_unified_models_detailed

    defaults = {
        (group["provider"], row["model_name"]): row["metadata"]["default"]
        for group in get_unified_models_detailed(model_type="decision")
        for row in group["models"]
    }
    assert defaults[("TypeSafe", "jev-latest")] is True
    assert defaults[("Perplexity", "pplx-decider-latest")] is True
    assert defaults[("OpenAI", "gpt-6-luna")] is True


def test_a_key_httpx_cant_send_is_refused_without_naming_its_characters(monkeypatch):
    sent = []
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *a, **_k: sent.append(a))
    with pytest.raises(DecisionConfigurationError, match="contains a character a key can't have") as caught:
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("boolean"), api_key="sk-key\u200b")
    assert "position" not in str(caught.value)
    assert sent == []


@pytest.mark.parametrize(
    ("code", "error"),
    [
        ("max_tokens_exceeded", DecisionEvaluationError),
        ("context_length_exceeded", DecisionEvaluationError),
        # Quoted text that mentions the code is not the code.
        ("invalid_value", DecisionConfigurationError),
    ],
)
def test_an_oversized_input_is_judged_by_its_error_code(monkeypatch, code, error):
    body = json.dumps({"error": {"code": code, "message": "instructions mention max_tokens_exceeded"}})
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *_a, **_k: httpx.Response(400, text=body))
    with pytest.raises(error) as caught:
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("boolean"), api_key="key")
    assert (getattr(caught.value, "category", None) == "input_too_large") is (error is DecisionEvaluationError)


@pytest.mark.parametrize("usage", [{"input_tokens": 290.0}, {"input_tokens": -1}, "not usage"])
def test_a_usage_block_langflow_cant_read_keeps_the_decision(usage):
    payload = {**response_for("TypeSafe", "boolean"), "usage": usage}
    result = providers.parse_response("TypeSafe", request_for("boolean"), payload)
    assert result.probability_true == 0.7
    assert result.usage is None


@pytest.mark.parametrize(("timeout", "ok"), [("30", True), ("", False), ("abc", False), (None, False)])
def test_a_timeout_sent_as_text_is_read_or_refused_plainly(monkeypatch, timeout, ok):
    monkeypatch.setattr(
        providers,
        "provider_safe_httpx_post",
        lambda *_a, **_k: httpx.Response(200, json=response_for("TypeSafe", "boolean")),
    )
    if ok:
        assert providers.evaluate_provider(
            "TypeSafe", "jev-latest", request_for("boolean"), api_key="k", timeout=timeout
        )
    else:
        with pytest.raises(DecisionConfigurationError, match="Timeout"):
            providers.evaluate_provider("TypeSafe", "jev-latest", request_for("boolean"), api_key="k", timeout=timeout)


@pytest.mark.parametrize(("key", "refused"), [("sk-server-env-key", True), ("sk-users-own-key", False)])
def test_a_key_check_never_sends_the_servers_key_to_a_saved_endpoint(monkeypatch, key, refused):
    """Switching a chat model on with only a saved base URL must not send the server's key there."""
    import sys
    import types

    from lfx.base.models.unified_models import validate_model_provider_key

    monkeypatch.setenv("OPENAI_API_KEY", "sk-server-env-key")
    monkeypatch.setattr("lfx.base.models.unified_models.credentials.validate_connector_url_for_ssrf", lambda _url: None)
    sent = []

    class Chat:
        def __init__(self, **kwargs):
            sent.append(kwargs.get("base_url"))

        def invoke(self, _prompt):
            return "ok"

    monkeypatch.setitem(sys.modules, "langchain_openai", types.SimpleNamespace(ChatOpenAI=Chat))
    variables = {"OPENAI_API_KEY": key, "OPENAI_BASE_URL": "https://attacker.example/v1"}
    if refused:
        with pytest.raises(ValueError, match="server-provisioned"):
            validate_model_provider_key("OpenAI", variables, "gpt-4o-mini", model_type="llm")
        assert sent == []
    else:
        validate_model_provider_key("OpenAI", variables, "gpt-4o-mini", model_type="llm")
        assert sent == ["https://attacker.example/v1"]


def test_a_key_with_a_line_break_is_refused_not_sent(monkeypatch):
    sent = []
    monkeypatch.setattr(providers, "provider_safe_httpx_post", lambda *a, **_k: sent.append(a))
    with pytest.raises(DecisionConfigurationError, match="contains a character a key can't have"):
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("boolean"), api_key="ts-abc\nts-abc")
    assert sent == []


def test_a_boolean_timeout_is_refused():
    with pytest.raises(DecisionConfigurationError, match="Timeout"):
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("boolean"), api_key="k", timeout=True)
