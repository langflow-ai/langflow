"""HTTP adapters for the documented hosted decision endpoints (no provider SDKs)."""

from __future__ import annotations

import json
import math
import re
import socket
from typing import TYPE_CHECKING, Annotated, Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lfx.base.models.decision_constants import DECISION_MODELS_DETAILED
from lfx.base.models.decisions.schema import (
    DecisionConfigurationError,
    DecisionEvaluationError,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    validation_summary,
)
from lfx.base.models.provider_ssrf import provider_safe_httpx_post
from lfx.base.models.unified_models.provider_queries import get_provider_secret_variable_key
from lfx.utils.secrets import secret_value_to_str
from lfx.utils.ssrf_protection import SSRFProtectionError

if TYPE_CHECKING:
    from collections.abc import Mapping

ENDPOINTS = {
    "TypeSafe": "https://api.typesafe.ai/v1/systemone",
    "Perplexity": "https://api.perplexity.ai/v1/decisions",
    "OpenAI": "https://api.openai.com/v1/decisions",
}
# Each provider's first catalog row is its default model.
DEFAULT_MODELS = {row["provider"]: row["name"] for row in reversed(DECISION_MODELS_DETAILED)}
MAX_HOSTED_SCORE_LEVELS = 10
MAX_CHOICES = 255
MAX_TIMEOUT = 300
# One question is sent per request, under this name.
QUESTION_ID = "decision"

OFFICIAL_OPENAI_BASE_URL = "https://api.openai.com/v1"
_OPENAI_BASE_URL_NAMES = ("OPENAI_BASE_URL", "OPENAI_API_BASE")


def require_official_openai_endpoint(*sources: Mapping[str, Any]) -> None:
    """OpenAI Decisions is only verified against the hosted API, never a custom base URL.

    Every source counts on its own, and so does the environment unless env fallback is off, so a
    blank or official value in one never hides a custom URL in another. A key meant for a proxy is
    therefore never sent to the official endpoint, whether by a run or by a key check.
    """
    from lfx.base.models.unified_models.credentials import provider_variable_from_env
    from lfx.services.variable.request_scope import is_env_fallback_disabled

    urls = [source.get(name) for source in sources for name in _OPENAI_BASE_URL_NAMES]
    if not is_env_fallback_disabled():
        urls += [provider_variable_from_env(name) for name in _OPENAI_BASE_URL_NAMES]
    for url in urls:
        configured_url = (secret_value_to_str(url, strip=True) or "").rstrip("/")
        if configured_url and configured_url != OFFICIAL_OPENAI_BASE_URL:
            msg = "OpenAI Decisions currently requires the official hosted endpoint."
            raise DecisionConfigurationError(msg)


def _answer_type(provider: str, kind: str) -> str:
    """The provider's name for a decision kind; only Boolean differs."""
    if kind != "boolean":
        return kind
    return "predicate" if provider == "OpenAI" else "noul"


def _description(candidate: DecisionOption) -> str:
    return f"{candidate.label}: {candidate.description}" if candidate.description else candidate.label


def _provider_error_code(response: httpx.Response) -> str:
    """A provider's machine-readable error code, only when it is a short safe token; never its message."""
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return ""
    code = error.get("code") or error.get("type") if isinstance(error, dict) else None
    return f", {code}" if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", code) else ""


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
    # TypeSafe and Perplexity document 10 levels. OpenAI publishes no cap, so the same
    # verified bound applies until a larger one is confirmed against the live API.
    if request.kind == "score" and len(request.levels) > MAX_HOSTED_SCORE_LEVELS:
        msg = f"{provider} decisions support at most {MAX_HOSTED_SCORE_LEVELS} score levels."
        raise DecisionConfigurationError(msg)
    if len(request.options) > MAX_CHOICES:
        msg = f"Decision Choice supports at most {MAX_CHOICES} options."
        raise DecisionConfigurationError(msg)
    question: dict[str, Any] = {"instructions": request.question, "type": _answer_type(provider, request.kind)}
    if provider == "OpenAI":
        question["name"] = QUESTION_ID
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
    if request.kind == "choice":
        question["criteria"] = {option.id: _description(option) for option in request.options}
    elif request.kind == "score":
        question["criteria"] = [_description(level) for level in request.levels]
    return {"model": model, "state": request.context, "questions": {QUESTION_ID: question}}


Count = Annotated[int, Field(strict=True, ge=0)]


class _InputDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cached_tokens: Count | None = None
    cache_write_tokens: Count | None = None


class _OutputDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reasoning_tokens: Count | None = None


class _Usage(BaseModel):
    """Only documented, non-negative token counts are kept."""

    model_config = ConfigDict(extra="ignore")

    input_tokens: Count | None = None
    output_tokens: Count | None = None
    total_tokens: Count | None = None
    input_tokens_details: _InputDetails | None = None
    output_tokens_details: _OutputDetails | None = None


def _token_usage(raw: Any) -> dict | None:
    return None if raw is None else _Usage.model_validate(raw).model_dump(exclude_none=True)


def parse_response(provider: str, request: DecisionRequest, payload: Any) -> DecisionResult:
    """Reject missing/mismatched evidence; never turn a malformed answer into uncertainty."""
    try:
        model = payload["model"]
        if not isinstance(model, str) or not model.strip():
            msg = "model must be a non-empty string"
            raise ValueError(msg)
        answers = payload["answers"]
        if provider == "OpenAI":
            if not isinstance(answers, list) or len(answers) != 1:
                msg = "answers must hold exactly one answer"
                raise ValueError(msg)
            answer = answers[0]
            if answer["name"] != QUESTION_ID:
                msg = "answer is for a different question"
                raise ValueError(msg)
        else:
            if not isinstance(answers, dict) or set(answers) != {QUESTION_ID}:
                msg = "answers must hold exactly the requested question"
                raise ValueError(msg)
            answer = answers[QUESTION_ID]
        common: dict[str, Any] = {
            "kind": request.kind,
            "provider": provider,
            "model": model,
            # Perplexity explicitly documents that this field echoes the requested alias.
            "model_source": "request" if provider == "Perplexity" else "response",
            "usage": _token_usage(payload.get("usage")),
        }
        # Only OpenAI documents a refusal answer. TypeSafe and Perplexity always answer with the
        # requested type, so any other type there is an invalid response, never a refusal.
        if provider == "OpenAI" and answer["type"] == "refusal":
            reason = answer.get("refusal")
            refusal = reason if isinstance(reason, str) and reason.strip() else None
            return DecisionResult(**common, status="refusal", refusal=refusal)
        expected_type = _answer_type(provider, request.kind)
        if answer["type"] != expected_type:
            # Never echo provider text: it reaches errors and evidence.
            msg = f"the answer type does not match the requested {expected_type!r}"
            raise ValueError(msg)
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
                    msg = "probabilities must be a list"
                    raise ValueError(msg)
                key = "value" if request.kind == "choice" else "label"
                mapped = {item[key]: item["probability"] for item in probabilities}
                if len(mapped) != len(probabilities):
                    msg = "probabilities repeat an option"
                    raise ValueError(msg)
                if request.kind == "score":
                    indices = {level.id: i for i, level in enumerate(request.levels)}
                    if any(
                        type(item["value"]) is not int or indices.get(item["label"]) != item["value"]
                        for item in probabilities
                    ):
                        msg = "score levels do not match their requested indices"
                        raise ValueError(msg)
                probabilities = mapped
            elif request.kind == "score":
                expected_keys = {str(i) for i in range(len(request.levels))}
                legend = {str(i): _description(level) for i, level in enumerate(request.levels)}
                if set(probabilities) != expected_keys or answer["legend"] != legend:
                    msg = "score levels or legend do not match the requested rubric"
                    raise ValueError(msg)
                probabilities = {level.id: probabilities[str(i)] for i, level in enumerate(request.levels)}
            result = DecisionResult(
                **common,
                probabilities=probabilities,
                confidence=answer.get("confidence"),
                selected_option=answer.get("choice") if request.kind == "choice" else None,
                score=answer["score"] if request.kind == "score" else None,
            )
        result.validate_for(request)
    except ValidationError as exc:
        detail = validation_summary(exc, field_only=True)
    except DecisionEvaluationError as exc:
        detail = str(exc)
    except KeyError as exc:
        detail = f"missing field {exc.args[0]!r}"
    except (TypeError, ValueError) as exc:
        detail = str(exc) or "unexpected answer shape"
    else:
        return result
    msg = f"{provider} returned an invalid decision response: {detail}."
    raise DecisionEvaluationError(msg, category="invalid_response")


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
        msg = f"A decision API key and timeout between 0 and {MAX_TIMEOUT} seconds are required."
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
        raise DecisionEvaluationError(msg, category="timeout") from None
    except SSRFProtectionError as exc:
        if not isinstance(exc.__cause__, socket.gaierror):
            # The official host resolved to a blocked address: a deployment problem, never routed to Else.
            msg = f"{provider} endpoint is blocked by SSRF protection."
            raise DecisionConfigurationError(msg) from None
        msg = f"{provider} decision request failed in transport (DNS resolution)."
        raise DecisionEvaluationError(msg, category="transport") from None
    except httpx.RequestError:
        msg = f"{provider} decision request failed in transport."
        raise DecisionEvaluationError(msg, category="transport") from None
    status = response.status_code
    code = _provider_error_code(response) if not response.is_success else ""
    # 402 is an unpaid or exhausted account: like a rejected key, it must stop rather than route to Else.
    if status in {401, 402, 403}:
        msg = f"{provider} denied the decision request (HTTP {status}{code})."
        raise PermissionError(msg)
    # An oversized input is a property of this message, not of the router, so the error action applies.
    if status == httpx.codes.REQUEST_ENTITY_TOO_LARGE or (
        status == httpx.codes.BAD_REQUEST and b"max_tokens_exceeded" in response.content
    ):
        msg = f"{provider} rejected the input as too large (HTTP {status}{code})."
        raise DecisionEvaluationError(msg, category="input_too_large")
    if status in {400, 404, 422}:
        msg = f"{provider} rejected the decision configuration (HTTP {status}{code})."
        raise DecisionConfigurationError(msg)
    if not response.is_success:
        msg = f"{provider} decision request failed (HTTP {status}{code})."
        raise DecisionEvaluationError(msg, category="http_error")
    try:
        body = json.loads(response.content, object_pairs_hook=_unique_json_object)
    except ValueError:
        msg = f"{provider} returned invalid or duplicate-key decision JSON."
        raise DecisionEvaluationError(msg, category="invalid_response") from None
    return parse_response(provider, request, body)


def validate_decision_provider_key(provider: str, variables: dict, model_name: str) -> None:
    """Validate explicit credentials with a minimal decision, never a chat completion."""
    if provider not in ENDPOINTS:
        msg = "Unsupported decision provider."
        raise ValueError(msg)
    api_key = secret_value_to_str(variables.get(get_provider_secret_variable_key(provider)), strip=True)
    if not api_key:
        msg = f"{provider} API key is required."
        raise ValueError(msg)
    request = DecisionRequest(kind="boolean", context="Connection check.", question="Does the text contain a check?")
    try:
        if provider == "OpenAI":
            require_official_openai_endpoint(variables)
        evaluate_provider(provider, model_name, request, api_key=api_key, timeout=15)
    except (DecisionConfigurationError, DecisionEvaluationError, PermissionError) as exc:
        raise ValueError(str(exc)) from None
