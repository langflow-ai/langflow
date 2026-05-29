"""Error handling and categorization for the Assistant API."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

MAX_ERROR_MESSAGE_LENGTH = 150
MIN_MEANINGFUL_PART_LENGTH = 10

# Substrings (case-insensitive) that identify a *model unavailable* error
# — e.g. OpenAI 403 model_not_found ("Project ... does not have access to
# model ..."), Anthropic equivalent, or a runtime check that flagged the
# selected model as missing from the provider's catalog. Used by the
# assistant streamer to decide whether to fall back to the next candidate
# model on the same provider.
_MODEL_UNAVAILABLE_MARKERS: tuple[str, ...] = (
    "model_not_found",
    "does not have access to model",
    "model is not available",
    "the model does not exist",
    "model not available",
    "no access to model",
)

ERROR_PATTERNS: list[tuple[list[str], str]] = [
    (
        ["rate_limit", "rate limit", "429", "consumption_limit"],
        "Rate limit exceeded. Please wait a moment and try again.",
    ),
    (["authentication", "api_key", "unauthorized", "401"], "Authentication failed. Check your API key."),
    (["quota", "billing", "insufficient"], "API quota exceeded. Please check your account billing."),
    (["timeout", "timed out"], "Request timed out. Please try again."),
    (["connection", "network"], "Connection error. Please check your network and try again."),
    (["500", "internal server error"], "Server error. Please try again later."),
]


def extract_friendly_error(error_msg: str) -> str:
    """Convert technical API errors into user-friendly messages."""
    error_lower = error_msg.lower()

    # Pydantic schema validation errors — checked BEFORE the generic pattern loop
    # so a message like "HTTPException 500: 1 validation error for InputSchema..."
    # is not masked by the "500" → "Server error" fallback.
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

    # Bug 4 [P2] — preserve diagnostic context. Many ``FlowExecutionError``s
    # arrive wrapped as ``"Error building Component X: <real cause>"``. The
    # default colon-split truncation would return the wrapper prefix and
    # discard the actually useful detail (PR-12575 Bug 4). Try to surface
    # the deepest meaningful cause before falling back to plain truncation.
    deep_cause = _extract_deepest_meaningful_cause(error_msg)
    if deep_cause:
        return _truncate_error_message(deep_cause)

    return _truncate_error_message(error_msg)


# Matches a Python-repr or JSON-style ``'message': '...'`` / ``"message": "..."``
# value as it appears in provider client error reprs (OpenAI, Anthropic, etc.).
_PROVIDER_MESSAGE_RE = re.compile(r"""['"]message['"]\s*:\s*['"]([^'"]+)['"]""")
# Generic wrapper prefixes whose body up to the first ``:`` is uninformative
# on its own — without unwrapping, the default colon-split truncation in
# ``_truncate_error_message`` returns just the wrapper (e.g. ``"Error
# building Component"`` / ``"Error running graph"``) and discards the
# underlying cause. Each entry must be a literal prefix the message lstrips
# to; the cause is the substring after the first ``:``.
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
           — return the part after the first colon (the underlying error
           the wrapper was trying to report). Recurse until no more
           wrappers match so nested wrappers (``Error running graph:
           Error building Component X: <real cause>``) fully unwrap to
           the root cause. Without this, the default colon-split
           truncation returns just the outer wrapper and the user sees
           something useless like ``"Error running graph"``.

    Returns None when neither pattern applies so callers fall back to the
    existing truncation behavior (zero behavior change for unwrapped errors).
    """
    match = _PROVIDER_MESSAGE_RE.search(error_msg)
    if match:
        return match.group(1).strip()

    current = error_msg
    unwrapped: str | None = None
    # Bounded loop: each iteration must strip at least one wrapper prefix
    # AND the remaining cause must be >= MIN_MEANINGFUL_PART_LENGTH. The
    # bound (5) is paranoia — real-world stacks rarely wrap more than 2
    # deep — but it guarantees this never loops on a pathological input.
    for _ in range(5):
        stripped_msg = current.lstrip()
        if ":" not in current or not any(stripped_msg.startswith(prefix) for prefix in _WRAPPER_PREFIXES):
            break
        # ``partition(":")`` keeps any embedded colons inside the cause (so
        # ``Error code: 403`` stays readable).
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
