"""Error handling and categorization for the Assistant API."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

MAX_ERROR_MESSAGE_LENGTH = 150
MIN_MEANINGFUL_PART_LENGTH = 10
MAX_RAW_CAUSE_LENGTH = 2000

# Case-insensitive markers of a *model unavailable* error (OpenAI 403 model_not_found,
# Anthropic equivalent, Ollama not-installed 404 / cloud-only 403) — drives model fallback.
_MODEL_UNAVAILABLE_MARKERS: tuple[str, ...] = (
    "model_not_found",
    "does not have access to model",
    "model is not available",
    "the model does not exist",
    "model not available",
    "no access to model",
    "not found (status code: 404)",
    "requires a subscription",
)

# (patterns, friendly message, recommendation) — patterns matched case-insensitively.
# ERROR_PATTERNS below preserves the historical (patterns, message) shape for consumers.
_ERROR_RULES: list[tuple[list[str], str, str]] = [
    (
        ["recursion limit", "graph_recursion_limit"],
        "The agent ran out of steps before finishing. Try again, or break the request into smaller parts.",
        "Break the request into smaller parts and try again.",
    ),
    (
        ["error parsing tool call"],
        "The model produced a malformed tool call. This is usually transient — please try again.",
        "Try again — this failure is usually transient.",
    ),
    (
        ["rate_limit", "rate limit", "429", "consumption_limit"],
        "Rate limit exceeded. Please wait a moment and try again.",
        "Wait a moment and retry the request.",
    ),
    (
        ["authentication", "api_key", "unauthorized", "401"],
        "Authentication failed. Check your API key.",
        "Check the API key in Settings → Model Providers.",
    ),
    (
        ["quota", "billing", "insufficient"],
        "API quota exceeded. Please check your account billing.",
        "Review your provider account's billing and quota.",
    ),
    (
        ["timeout", "timed out"],
        "Request timed out. Please try again.",
        "Try again; if it keeps timing out, check the provider's status.",
    ),
    (
        ["connection", "network"],
        "Connection error. Please check your network and try again.",
        "Check your network connection and try again.",
    ),
    (
        ["500", "internal server error"],
        "Server error. Please try again later.",
        "Try again later — the provider reported an internal error.",
    ),
]

ERROR_PATTERNS: list[tuple[list[str], str]] = [(patterns, message) for patterns, message, _ in _ERROR_RULES]


def extract_friendly_error(error_msg: str) -> str:
    """Convert technical API errors into user-friendly messages."""
    error_lower = error_msg.lower()

    # Checked BEFORE the pattern loop so "HTTPException 500: 1 validation error for
    # InputSchema..." is not masked by the "500" → "Server error" fallback.
    schema_error_terms = ("validation error for", "input should be a valid", "pydantic.validationerror")
    if any(term in error_lower for term in schema_error_terms):
        return (
            "The selected model produced output that didn't match the expected schema. "
            "Try again or use a more capable model."
        )

    for patterns, friendly_message in ERROR_PATTERNS:
        if any(pattern in error_lower or pattern in error_msg for pattern in patterns):
            return friendly_message

    model_missing_terms = ("not found", "does not exist", "not available")
    if "model" in error_lower and any(term in error_lower for term in model_missing_terms):
        return "Model not available. Please select a different model."

    if "content" in error_lower and any(term in error_lower for term in ["filter", "policy", "safety"]):
        return "Request blocked by content policy. Please modify your prompt."

    # PR-12575 Bug 4 — surface the deepest meaningful cause before plain truncation,
    # so "Error building Component X: <real cause>" doesn't collapse to the wrapper.
    deep_cause = _extract_deepest_meaningful_cause(error_msg)
    if deep_cause:
        return _truncate_error_message(deep_cause)

    return _truncate_error_message(error_msg)


# Python-repr / JSON ``'message': '...'`` value as it appears in provider client error reprs.
_PROVIDER_MESSAGE_RE = re.compile(r"""['"]message['"]\s*:\s*['"]([^'"]+)['"]""")
# Wrapper prefixes whose body up to the first ``:`` is uninformative on its own;
# the actionable cause is the substring after the first colon.
_WRAPPER_PREFIXES: tuple[str, ...] = (
    "Error building Component",
    "Error running graph",
)


def _extract_deepest_meaningful_cause(error_msg: str) -> str | None:
    """Pull the actionable cause out of a wrapped error message.

    Strategy (first match wins):
        1. If the message embeds a Python-repr / JSON ``'message': '...'``
           value (OpenAI, Anthropic, similar) — return that. This is the
           single most actionable string the user can read.
        2. If the message is wrapped with one of the known prefixes
           (``Error building Component X: …``, ``Error running graph: …``)
           — return the part after the first colon, recursing until no more
           wrappers match so nested wrappers fully unwrap to the root cause.

    Returns None when neither pattern applies so callers fall back to the
    existing truncation behavior (zero behavior change for unwrapped errors).
    """
    match = _PROVIDER_MESSAGE_RE.search(error_msg)
    if match:
        return match.group(1).strip()

    current = error_msg
    unwrapped: str | None = None
    # Bounded to 5 unwraps as paranoia against pathological input; real stacks rarely wrap >2 deep.
    for _ in range(5):
        stripped_msg = current.lstrip()
        if ":" not in current or not any(stripped_msg.startswith(prefix) for prefix in _WRAPPER_PREFIXES):
            break
        # partition keeps embedded colons inside the cause (e.g. "Error code: 403").
        _wrapper, _, cause = current.partition(":")
        cause = cause.strip()
        if len(cause) < MIN_MEANINGFUL_PART_LENGTH:
            break
        unwrapped = cause
        current = cause

    return unwrapped


def _truncate_error_message(error_msg: str) -> str:
    """Truncate long error messages, preserving meaningful content."""
    if len(error_msg) <= MAX_ERROR_MESSAGE_LENGTH:
        return error_msg

    if ":" in error_msg:
        for part in error_msg.split(":"):
            stripped = part.strip()
            if MIN_MEANINGFUL_PART_LENGTH < len(stripped) < MAX_ERROR_MESSAGE_LENGTH:
                return stripped

    return f"{error_msg[:MAX_ERROR_MESSAGE_LENGTH]}..."


_COMPONENT_WRAPPER_RE = re.compile(r"Error building Component ([^:\n]+):")
_TOOL_NAME_RE = re.compile(r"""tool ['"]([\w.\- ]+)['"]""", re.IGNORECASE)


def get_error_recommendation(error_msg: str) -> str | None:
    """Return the recommended next step for a known error category, else None."""
    error_lower = error_msg.lower()
    for patterns, _message, recommendation in _ERROR_RULES:
        if any(pattern in error_lower or pattern in error_msg for pattern in patterns):
            return recommendation
    return None


def build_error_detail(
    raw_error: str | None, *, step: str | None = None, include_raw_cause: bool = False
) -> dict[str, str] | None:
    """Build the additive ``detail`` object for the SSE error event.

    Fields (all optional): ``step`` (last progress step emitted),
    ``component_id`` / ``tool`` (when extractable from the raw message),
    ``raw_cause`` (pre-truncation error, capped at ``MAX_RAW_CAUSE_LENGTH``),
    ``recommendation`` (mapped from the known error categories).
    Returns None when there is nothing to report so the ``error`` event
    payload stays byte-identical for every current case.

    SECURITY: ``raw_cause`` is the raw internal error — the string
    FlowExecutionError deliberately keeps out of public HTTP detail. It is
    emitted only when ``include_raw_cause=True`` (caller verified the
    requesting user is a superuser); every other field stays for everyone.
    """
    detail: dict[str, str] = {}
    if step:
        detail["step"] = step
    if raw_error:
        component_match = _COMPONENT_WRAPPER_RE.search(raw_error)
        if component_match:
            detail["component_id"] = component_match.group(1).strip()
        tool_match = _TOOL_NAME_RE.search(raw_error)
        if tool_match:
            detail["tool"] = tool_match.group(1).strip()
        if include_raw_cause:
            detail["raw_cause"] = raw_error[:MAX_RAW_CAUSE_LENGTH]
        recommendation = get_error_recommendation(raw_error)
        if recommendation:
            detail["recommendation"] = recommendation
    return detail or None


def is_model_unavailable_error(error_msg: str | None) -> bool:
    """Return True when the underlying error indicates the selected model is unreachable.

    Drives the assistant's model-fallback chain: a True result means the
    streamer should swap to the next candidate on the same provider rather
    than surface the error to the user (auth / network / rate-limit errors
    intentionally do NOT match — they would recur on the next model and
    mask the real problem).

    Why: PR-12575 Bug 1 — OpenAI 403 ``model_not_found`` (catalog default
    not enabled for the user's project) was reaching the SSE error event
    as the generic ``Error building Component Agent`` instead of trying a
    sibling model.
    """
    if not error_msg:
        return False
    lowered = error_msg.lower()
    return any(marker in lowered for marker in _MODEL_UNAVAILABLE_MARKERS)


def is_transient_tool_call_error(error_msg: str | None) -> bool:
    """True for runtime tool-call parse failures (Ollama 500) — resampling usually fixes them."""
    return bool(error_msg) and "error parsing tool call" in error_msg.lower()


def format_models_exhausted_message(provider: str, tried_models: Iterable[str]) -> str:
    """Build the user-facing error when every model on a provider was tried.

    Names the provider and lists the exhausted models so the user can
    request access to one of them or switch providers. Replaces the
    pre-fix generic ``Error building Component Agent`` from Bug 1.
    """
    models = [m for m in tried_models if m]
    models_str = ", ".join(models) if models else "(none)"
    return (
        f"No accessible model on {provider}. Tried: {models_str}. "
        f"Configure access to one of these models in your {provider} account, "
        f"or switch to a different provider in Settings → Model Providers."
    )


def build_recovered_notice(
    kind: str,
    failed_model: str | None,
    raw_error: str | None,
    used_model: str | None,
) -> dict[str, str]:
    """Shape a non-fatal "your model failed, the turn recovered" notice.

    Emitted on the complete event so the UI can show an (i) instead of hiding a
    silent background swap. ``kind`` is ``model_fallback`` (swapped to another
    model) or ``model_remediation`` (retried the same model with adjusted params).
    """
    reason = extract_friendly_error(raw_error) if raw_error else "Model error"
    notice: dict[str, str] = {"type": kind, "reason": reason}
    if failed_model:
        notice["failed_model"] = failed_model
    if used_model and used_model != failed_model:
        notice["used_model"] = used_model
    return notice
