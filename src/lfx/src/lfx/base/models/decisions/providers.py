"""HTTP adapters for the documented hosted decision endpoints (no provider SDKs)."""

from __future__ import annotations

import json
import math
from typing import Any

import httpx

from lfx.base.models.decisions.schema import (
    DecisionConfigurationError,
    DecisionEvaluationError,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
)
from lfx.base.models.provider_ssrf import provider_safe_httpx_post
from lfx.utils.ssrf_protection import SSRFProtectionError

ENDPOINTS = {
    "TypeSafe": "https://api.typesafe.ai/v1/systemone",
    "Perplexity": "https://api.perplexity.ai/v1/decisions",
    "OpenAI": "https://api.openai.com/v1/decisions",
}
DEFAULT_MODELS = {
    "TypeSafe": "jev-latest",
    "Perplexity": "pplx-decider-latest",
    "OpenAI": "gpt-6-luna",
}
MAX_HOSTED_SCORE_LEVELS = 10
MAX_CHOICES = 255
MAX_TIMEOUT = 300

API_KEY_VARIABLES = {
    "TypeSafe": "TYPESAFE_API_KEY",
    "Perplexity": "PERPLEXITY_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
}
OFFICIAL_OPENAI_BASE_URL = "https://api.openai.com/v1"


def require_official_openai_endpoint(variables: dict[str, Any]) -> None:
    """OpenAI Decisions is only verified against the hosted API, never a custom base URL."""
    for name in ("OPENAI_BASE_URL", "OPENAI_API_BASE"):
        configured_url = str(variables.get(name) or "").rstrip("/")
        if configured_url and configured_url != OFFICIAL_OPENAI_BASE_URL:
            msg = "OpenAI Decisions currently requires the official hosted endpoint."
            raise DecisionConfigurationError(msg)


def _description(candidate: DecisionOption) -> str:
    return f"{candidate.label}: {candidate.description}" if candidate.description else candidate.label


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            msg = "Duplicate JSON key in decision response."
            raise ValueError(msg)
        result[key] = value
    return result


def build_payload(provider: str, model: str, request: DecisionRequest) -> dict[str, Any]:
    """Translate one typed question, retaining option identity independently of display text."""
    if provider not in ENDPOINTS:
        msg = "Unsupported decision provider."
        raise DecisionConfigurationError(msg)
    if (
        provider in {"TypeSafe", "Perplexity"}
        and request.kind == "score"
        and len(request.levels) > MAX_HOSTED_SCORE_LEVELS
    ):
        msg = f"{provider} supports at most 10 score levels."
        raise DecisionConfigurationError(msg)
    if len(request.options) > MAX_CHOICES:
        msg = "Decision Choice supports at most 255 options."
        raise DecisionConfigurationError(msg)
    question: dict[str, Any] = {"instructions": request.question}
    if provider == "OpenAI":
        question.update(type="predicate" if request.kind == "boolean" else request.kind, name=request.question_id)
        if request.kind == "choice":
            question["choices"] = [
                {"value": option.id, "description": _description(option)} for option in request.options
            ]
        elif request.kind == "score":
            question["levels"] = [{"label": level.id, "description": _description(level)} for level in request.levels]
        context = request.context
        if not isinstance(context, str):
            context = json.dumps(context, ensure_ascii=False, allow_nan=False)
        return {"model": model, "input": context, "questions": [question]}
    question["type"] = "noul" if request.kind == "boolean" else request.kind
    if request.kind == "choice":
        question["criteria"] = {option.id: _description(option) for option in request.options}
    elif request.kind == "score":
        question["criteria"] = [_description(level) for level in request.levels]
    return {"model": model, "state": request.context, "questions": {request.question_id: question}}


def _token_usage(raw: Any) -> dict | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise TypeError
    result: dict[str, Any] = {}
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        if name in raw:
            count = raw[name]
            if type(count) is not int or count < 0:
                raise ValueError
            result[name] = count
    for name, allowed in (
        ("input_tokens_details", ("cached_tokens", "cache_write_tokens")),
        ("output_tokens_details", ("reasoning_tokens",)),
    ):
        if name in raw:
            if not isinstance(raw[name], dict):
                raise TypeError
            details = {}
            for key in allowed:
                if key in raw[name]:
                    count = raw[name][key]
                    if type(count) is not int or count < 0:
                        raise ValueError
                    details[key] = count
            result[name] = details
    return result


def parse_response(provider: str, request: DecisionRequest, payload: Any) -> DecisionResult:
    """Reject missing/mismatched evidence; never turn a malformed answer into uncertainty."""
    try:
        model = payload["model"]
        if not isinstance(model, str) or not model.strip():
            raise ValueError
        answers = payload["answers"]
        if provider == "OpenAI":
            if not isinstance(answers, list) or len(answers) != 1:
                raise ValueError
            answer = answers[0]
            if answer["name"] != request.question_id:
                raise ValueError
        else:
            if not isinstance(answers, dict) or set(answers) != {request.question_id}:
                raise ValueError
            answer = answers[request.question_id]
        common: dict[str, Any] = {
            "kind": request.kind,
            "question_id": request.question_id,
            "provider": provider,
            "model": model,
            # Perplexity explicitly documents that this field echoes the requested alias.
            "model_source": "request" if provider == "Perplexity" else "response",
            "usage": _token_usage(payload.get("usage")),
        }
        if provider == "OpenAI" and answer["type"] == "refusal":
            reason = answer.get("refusal")
            if not isinstance(reason, str) or not reason.strip():
                reason = "Provider declined this question."
            return DecisionResult(**common, status="refusal", refusal=reason)
        expected_type: str = request.kind
        if request.kind == "boolean":
            expected_type = "predicate" if provider == "OpenAI" else "noul"
        if answer["type"] != expected_type:
            raise ValueError
        if request.kind == "boolean":
            result = DecisionResult(
                **common,
                probability_true=answer["probability" if provider == "OpenAI" else "noul"],
                confidence=answer.get("confidence"),
            )
        else:
            probabilities = answer["probabilities"]
            if provider == "OpenAI":
                if not isinstance(probabilities, list):
                    raise ValueError
                key = "value" if request.kind == "choice" else "label"
                mapped = {item[key]: item["probability"] for item in probabilities}
                if len(mapped) != len(probabilities):
                    raise ValueError
                if request.kind == "score":
                    indices = {level.id: i for i, level in enumerate(request.levels)}
                    if any(
                        type(item["value"]) is not int or indices.get(item["label"]) != item["value"]
                        for item in probabilities
                    ):
                        raise ValueError
                probabilities = mapped
            elif request.kind == "score":
                expected_keys = {str(i) for i in range(len(request.levels))}
                legend = {str(i): _description(level) for i, level in enumerate(request.levels)}
                if set(probabilities) != expected_keys or answer["legend"] != legend:
                    raise ValueError
                probabilities = {level.id: probabilities[str(i)] for i, level in enumerate(request.levels)}
            result = DecisionResult(
                **common,
                probabilities=probabilities,
                confidence=answer.get("confidence"),
                selected_option=answer.get("choice") if request.kind == "choice" else None,
                score=answer["score"] if request.kind == "score" else None,
            )
        result.validate_for(request)
    except (KeyError, TypeError, ValueError, DecisionEvaluationError):
        msg = f"{provider} returned an invalid decision response."
        raise DecisionEvaluationError(msg) from None
    else:
        return result


def evaluate_provider(
    provider: str,
    model: str,
    request: DecisionRequest,
    *,
    api_key: str,
    timeout: float = 60,
) -> DecisionResult:
    """Execute one request through the existing strict SSRF-protected transport."""
    payload = build_payload(provider, model, request)
    if not api_key or not math.isfinite(timeout) or timeout <= 0 or timeout > MAX_TIMEOUT:
        msg = "A decision API key and timeout between 0 and 300 seconds are required."
        raise DecisionConfigurationError(msg)
    try:
        response = provider_safe_httpx_post(
            ENDPOINTS[provider],
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            follow_redirects=False,
        )
    except httpx.TimeoutException:
        msg = f"{provider} decision request timed out."
        raise DecisionEvaluationError(msg) from None
    except (httpx.RequestError, SSRFProtectionError):
        msg = f"{provider} decision request failed in transport."
        raise DecisionEvaluationError(msg) from None
    if response.status_code in {401, 403}:
        msg = f"{provider} denied the decision request (HTTP {response.status_code})."
        raise PermissionError(msg)
    if response.status_code in {400, 404, 413, 422}:
        msg = f"{provider} rejected the decision configuration (HTTP {response.status_code})."
        raise DecisionConfigurationError(msg)
    if not response.is_success:
        msg = f"{provider} decision request failed (HTTP {response.status_code})."
        raise DecisionEvaluationError(msg)
    try:
        body = json.loads(response.content, object_pairs_hook=_unique_json_object)
    except ValueError:
        msg = f"{provider} returned invalid or duplicate-key decision JSON."
        raise DecisionEvaluationError(msg) from None
    return parse_response(provider, request, body)


def validate_decision_provider_key(provider: str, variables: dict, model_name: str) -> None:
    """Validate explicit credentials with a minimal decision, never a chat completion."""
    if provider not in API_KEY_VARIABLES:
        msg = "Unsupported decision provider."
        raise ValueError(msg)
    api_key = variables.get(API_KEY_VARIABLES[provider])
    if hasattr(api_key, "get_secret_value"):
        api_key = api_key.get_secret_value()
    if not isinstance(api_key, str) or not api_key.strip():
        msg = f"{provider} API key is required."
        raise ValueError(msg)
    request = DecisionRequest(kind="boolean", context="Connection check.", question="Does the text contain a check?")
    try:
        if provider == "OpenAI":
            require_official_openai_endpoint(variables)
        evaluate_provider(provider, model_name, request, api_key=api_key, timeout=15)
    except (DecisionConfigurationError, DecisionEvaluationError, PermissionError) as exc:
        raise ValueError(str(exc)) from None
