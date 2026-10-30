"""HTTP adapters for the documented hosted decision endpoints (no provider SDKs)."""

from __future__ import annotations

import json
import math
import re
import socket
from typing import TYPE_CHECKING, Annotated, Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lfx.base.models.decisions.schema import (
    DecisionConfigurationError,
    DecisionEvaluationError,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    validation_summary,
)
from lfx.base.models.provider_ssrf import provider_safe_httpx_post
from lfx.base.models.unified_models.credentials import provider_variable_from_env
from lfx.base.models.unified_models.provider_queries import get_provider_secret_variable_key
from lfx.services.variable.request_scope import (
    get_effective_request_variables,
    is_env_fallback_disabled,
    variable_name_forms,
)
from lfx.utils.secrets import secret_value_to_str
from lfx.utils.ssrf_protection import SSRFProtectionError

if TYPE_CHECKING:
    from collections.abc import Mapping

ENDPOINTS = {
    "TypeSafe": "https://api.typesafe.ai/v1/systemone",
    "Perplexity": "https://api.perplexity.ai/v1/decisions",
    "OpenAI": "https://api.openai.com/v1/decisions",
}
MAX_HOSTED_SCORE_LEVELS = 10
MAX_CHOICES = 255
MAX_TIMEOUT = 300
# One question is sent per request, under this name.
QUESTION_ID = "decision"

OFFICIAL_OPENAI_BASE_URL = "https://api.openai.com/v1"
# Requests may send each name in any form a request variable takes (see variable_name_forms).
_OPENAI_BASE_URL_NAMES = tuple(
    name for base in ("OPENAI_BASE_URL", "OPENAI_API_BASE") for name in variable_name_forms(base)
)


def require_official_openai_endpoint(*sources: Mapping[str, Any]) -> None:
    """OpenAI Decisions is only verified against the hosted API, never a custom base URL.

    Every source counts on its own, as do the active request scope and, unless env fallback is off,
    the environment, so a blank or official value in one never hides a custom URL in another. A key
    meant for a proxy is therefore never sent to the official endpoint, by a run or by a key check.
    """
    # The same request variables a key comes from, including the LANGFLOW_REQUEST_VARIABLES fallback.
    sources = (*sources, get_effective_request_variables())
    urls = [source.get(name) for source in sources for name in _OPENAI_BASE_URL_NAMES]
    if not is_env_fallback_disabled():
        urls += [provider_variable_from_env(name) for name in _OPENAI_BASE_URL_NAMES]
    for url in urls:
        configured_url = (secret_value_to_str(url, strip=True) or "").rstrip("/")
        if configured_url and configured_url != OFFICIAL_OPENAI_BASE_URL:
            msg = (
                "OpenAI decision models only work with the official OpenAI endpoint. Clear the custom OpenAI "
                "base URL, or pick another Decision Model."
            )
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


def _request_id(response: httpx.Response) -> str | None:
    """The provider's ``x-request-id``, only when it is a short safe token; never other header content."""
    value = response.headers.get("x-request-id")
    return value if value and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) else None


def _reference(status: int | None = None, code: str = "", request_id: str | None = None) -> str:
    """A trailing reference such as " (HTTP 401, invalid_api_key, request ID req_1)", or nothing."""
    parts = [f"HTTP {status}{code}"] if status else []
    if request_id:
        parts.append(f"request ID {request_id}")
    return f" ({', '.join(parts)})" if parts else ""


def _try_again(provider: str, request_id: str | None) -> str:
    contact = f"contact {provider} with the request ID" if request_id else f"contact {provider}"
    return f"Try again; if it keeps happening, {contact}."


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
        msg = f"{provider} has no decision models."
        raise DecisionConfigurationError(msg)
    # TypeSafe and Perplexity document 10 levels. OpenAI publishes no cap, so the same
    # verified bound applies until a larger one is confirmed against the live API.
    if request.kind == "score" and len(request.levels) > MAX_HOSTED_SCORE_LEVELS:
        msg = f"{provider} supports at most {MAX_HOSTED_SCORE_LEVELS} Score levels."
        raise DecisionConfigurationError(msg)
    if len(request.options) > MAX_CHOICES:
        msg = f"Choice supports at most {MAX_CHOICES} options."
        raise DecisionConfigurationError(msg)
    question: dict[str, Any] = {"instructions": request.question, "type": _answer_type(provider, request.kind)}
    if request.yes_description or request.no_description:
        # Only TypeSafe and Perplexity document what a Boolean's outcomes mean.
        if provider == "OpenAI":
            msg = (
                "OpenAI decision models take no descriptions of what Yes and No mean. Clear What Yes Means "
                "and What No Means, or pick another Decision Model."
            )
            raise DecisionConfigurationError(msg)
        outcomes = (("true", request.yes_description), ("false", request.no_description))
        question["criteria"] = {outcome: text for outcome, text in outcomes if text}
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
    # Usage isn't decision evidence: a block Langflow can't read is dropped, never the decision.
    try:
        return None if raw is None else _Usage.model_validate(raw).model_dump(exclude_none=True)
    except ValidationError:
        return None


def parse_response(
    provider: str, request: DecisionRequest, payload: Any, *, request_id: str | None = None
) -> DecisionResult:
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
            "request_id": request_id,
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
    msg = f"{provider} sent an answer Langflow couldn't use{_reference(request_id=request_id)}: {detail}. "
    raise DecisionEvaluationError(msg + _try_again(provider, request_id), category="invalid_response")


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
    if not api_key:
        msg = f"Add the {provider} API key in Model Providers."
        raise DecisionConfigurationError(msg)
    if not (api_key.isascii() and api_key.isprintable()):
        # httpx can't send it, and its error would name the character's position in the key.
        msg = f"The {provider} API key contains a character a key can't have. Paste it again."
        raise DecisionConfigurationError(msg)
    # An API tweak can send the timeout as text; a Boolean is not a number of seconds.
    try:
        timeout = math.nan if isinstance(timeout, bool) else float(timeout)
    except (TypeError, ValueError):
        timeout = math.nan
    if not math.isfinite(timeout) or timeout <= 0 or timeout > MAX_TIMEOUT:
        msg = f"Timeout (seconds) must be more than 0 and at most {MAX_TIMEOUT}."
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
        msg = f"{provider} didn't answer in time. Try again."
        raise DecisionEvaluationError(msg, category="timeout") from None
    except SSRFProtectionError as exc:
        if not isinstance(exc.__cause__, socket.gaierror):
            # The official host resolved to a blocked address: a deployment problem, never routed to Else.
            msg = f"This server's network security settings block {provider}'s endpoint. Ask an administrator."
            raise DecisionConfigurationError(msg) from None
        msg = (
            f"Langflow couldn't reach {provider} (the DNS lookup failed). Check this server's network, then try again."
        )
        raise DecisionEvaluationError(msg, category="transport") from None
    except httpx.RequestError:
        msg = f"Langflow couldn't reach {provider}. Check this server's network, then try again."
        raise DecisionEvaluationError(msg, category="transport") from None
    status = response.status_code
    request_id = _request_id(response)
    # Failures end with the HTTP status, the provider's code and its request ID, to raise with the provider.
    code = "" if response.is_success else _provider_error_code(response)
    ref = "" if response.is_success else _reference(status, code, request_id)
    # 402 is an unpaid or exhausted account, which OpenAI reports as 429 insufficient_quota: like a
    # rejected key, it must stop rather than route to Else.
    out_of_credit = status == httpx.codes.PAYMENT_REQUIRED or (
        status == httpx.codes.TOO_MANY_REQUESTS and code == ", insufficient_quota"
    )
    if status == httpx.codes.UNAUTHORIZED:
        msg = f"{provider} didn't accept the API key{ref}. Check the {provider} API key in Model Providers."
        raise PermissionError(msg)
    if out_of_credit:
        msg = f"{provider} declined the request because of the account's billing or credit{ref}. Check your plan."
        raise PermissionError(msg)
    if status == httpx.codes.FORBIDDEN:
        msg = f"This {provider} API key can't use decision models{ref}. Use a key with access to them."
        raise PermissionError(msg)
    # An oversized input is a property of this message, not of the router, so the error action applies.
    # TypeSafe reports it as 400 max_tokens_exceeded; OpenAI's other APIs as 400 context_length_exceeded,
    # assumed for its Decisions API too.
    if status == httpx.codes.REQUEST_ENTITY_TOO_LARGE or (
        status == httpx.codes.BAD_REQUEST and code in {", max_tokens_exceeded", ", context_length_exceeded"}
    ):
        msg = f"{provider} rejected the input as too large{ref}. Shorten the input."
        raise DecisionEvaluationError(msg, category="input_too_large")
    if status == httpx.codes.NOT_FOUND:
        msg = (
            f"{provider} doesn't offer this decision model to this API key{ref}. "
            "Pick another Decision Model, or check the key's access."
        )
        raise DecisionConfigurationError(msg)
    if status in {400, 422}:
        msg = f"{provider} couldn't accept this decision request{ref}. Check the Decision Model and its settings."
        raise DecisionConfigurationError(msg)
    if status == httpx.codes.TOO_MANY_REQUESTS:
        msg = f"{provider} is rate-limiting this API key{ref}. Wait a moment, then try again."
        raise DecisionEvaluationError(msg, category="http_error")
    if status >= httpx.codes.INTERNAL_SERVER_ERROR:
        msg = f"{provider} had a server problem{ref}. Try again later."
        raise DecisionEvaluationError(msg, category="http_error")
    if not response.is_success:
        msg = f"{provider} decision request failed{ref}."
        raise DecisionEvaluationError(msg, category="http_error")
    try:
        body = json.loads(response.content, object_pairs_hook=_unique_json_object)
    except ValueError:
        msg = f"{provider} sent an answer Langflow couldn't read{_reference(request_id=request_id)}. "
        raise DecisionEvaluationError(msg + _try_again(provider, request_id), category="invalid_response") from None
    return parse_response(provider, request, body, request_id=request_id)


def validate_decision_provider_key(provider: str, variables: dict, model_name: str) -> None:
    """Validate explicit credentials with a minimal decision, never a chat completion."""
    if provider not in ENDPOINTS:
        msg = f"{provider} has no decision models."
        raise ValueError(msg)
    api_key = secret_value_to_str(variables.get(get_provider_secret_variable_key(provider)), strip=True)
    if not api_key:
        msg = f"Enter the {provider} API key."
        raise ValueError(msg)
    request = DecisionRequest(kind="boolean", context="Connection check.", question="Does the text contain a check?")
    try:
        if provider == "OpenAI":
            require_official_openai_endpoint(variables)
        evaluate_provider(provider, model_name, request, api_key=api_key, timeout=15)
    except (DecisionConfigurationError, DecisionEvaluationError, PermissionError) as exc:
        raise ValueError(str(exc)) from None
