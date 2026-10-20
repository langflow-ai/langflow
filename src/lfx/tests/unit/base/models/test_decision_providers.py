"""Documented provider fixtures exercise wire translation without paid inference."""

import copy

import httpx
import pytest
from lfx.base.models.decisions import providers
from lfx.base.models.decisions.schema import (
    DecisionConfigurationError,
    DecisionEvaluationError,
    DecisionOption,
    DecisionRequest,
)

PROVIDERS = tuple(providers.ENDPOINTS)


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
        "model": providers.DEFAULT_MODELS[provider],
        "answers": [answer] if provider == "OpenAI" else {"decision": answer},
    }


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("kind", ["choice", "boolean", "score"])
def test_wire_contract(provider, kind):
    request = request_for(kind)
    payload = providers.build_payload(provider, providers.DEFAULT_MODELS[provider], request)
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
    with pytest.raises(DecisionEvaluationError, match="invalid decision response") as error:
        providers.parse_response(provider, request_for("choice"), body)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("provider", ["TypeSafe", "Perplexity"])
def test_hosted_score_level_limit(provider):
    request = DecisionRequest(
        kind="score",
        context="text",
        question="rate",
        levels=tuple(DecisionOption(id=str(i), label=f"Level {i}") for i in range(11)),
    )
    with pytest.raises(DecisionConfigurationError, match="10 score levels"):
        providers.build_payload(provider, providers.DEFAULT_MODELS[provider], request)


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
    with pytest.raises(ValueError, match="API key is required"):
        providers.validate_decision_provider_key("OpenAI", {}, "gpt-6-luna")
    with pytest.raises(ValueError, match="official hosted endpoint"):
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
    with pytest.raises(DecisionEvaluationError, match="invalid decision response"):
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
    with pytest.raises(DecisionEvaluationError, match="duplicate-key"):
        providers.evaluate_provider(provider, providers.DEFAULT_MODELS[provider], request_for("choice"), api_key="key")


@pytest.mark.parametrize("provider", ["TypeSafe", "Perplexity"])
def test_score_legend_must_preserve_requested_order(provider):
    body = response_for(provider, "score")
    body["answers"]["decision"]["legend"] = {"0": "High", "1": "Low"}
    with pytest.raises(DecisionEvaluationError, match="invalid decision response"):
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
        providers.build_payload(provider, providers.DEFAULT_MODELS[provider], request)


@pytest.mark.parametrize("timeout", [0, -1, 301, float("nan"), float("inf")])
def test_invalid_timeout_fails_before_transport(timeout):
    with pytest.raises(DecisionConfigurationError, match="timeout"):
        providers.evaluate_provider("OpenAI", "gpt-6-luna", request_for("boolean"), api_key="key", timeout=timeout)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_credential_validation_uses_explicit_key_and_boolean_request(provider, monkeypatch):
    calls = []
    monkeypatch.setenv(providers.API_KEY_VARIABLES[provider], "server-secret")
    monkeypatch.setattr(providers, "evaluate_provider", lambda *args, **kwargs: calls.append((args, kwargs)))
    providers.validate_decision_provider_key(
        provider, {providers.API_KEY_VARIABLES[provider]: "tenant-key"}, providers.DEFAULT_MODELS[provider]
    )
    args, kwargs = calls.pop()
    assert args[0] == provider
    assert args[1] == providers.DEFAULT_MODELS[provider]
    assert args[2].kind == "boolean"
    assert kwargs == {"api_key": "tenant-key", "timeout": 15}


def test_ssrf_resolution_failure_is_operational(monkeypatch):
    from lfx.utils.ssrf_protection import SSRFProtectionError

    def post(*_args, **_kwargs):
        msg = "DNS resolution failed for secret.internal"
        raise SSRFProtectionError(msg)

    monkeypatch.setattr(providers, "provider_safe_httpx_post", post)
    with pytest.raises(DecisionEvaluationError) as caught:
        providers.evaluate_provider("TypeSafe", "jev-latest", request_for("choice"), api_key="key")
    assert "secret" not in str(caught.value)


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
