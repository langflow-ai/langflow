"""Classify a failed verification-run error as fixable or not.

The flow-verification loop runs a freshly built flow for real. When the
run fails it must decide whether to spend another LLM attempt fixing it.
Retrying a missing user credential / DB / file / network error (or a
timeout) only burns tokens — only genuine code/wiring/spec bugs are
worth feeding back to the agent. This module is the pure decision; it
performs no I/O and logs nothing (callers scrub secrets before logging).
"""

from __future__ import annotations

from enum import Enum


class RunErrorKind(Enum):
    """Why a verification run failed, from the loop's point of view."""

    FIXABLE = "fixable"  # code/wiring/spec bug — feed back to the agent
    EXTERNAL_RESOURCE = "external_resource"  # needs a resource we can't supply
    TIMEOUT = "timeout"  # ran too long — don't loop (no 6-min requests)
    UNKNOWN = "unknown"  # unmatched — caller bounds attempts via the cap


# Specific to the run engine's "The flow run timed out after Ns." — a
# generic "timed out" would wrongly steal "connection timed out" (a DB /
# network resource error, which must stay EXTERNAL_RESOURCE).
_TIMEOUT_MARKERS: tuple[str, ...] = (
    "timed out after",
    "flow run timed out",
)

# Checked BEFORE the external markers so a code bug whose text happens to
# contain "api key" (e.g. `KeyError: 'api_key'` — a missing spec key, not
# a missing credential) is correctly treated as fixable.
_FIXABLE_MARKERS: tuple[str, ...] = (
    "attributeerror",
    "typeerror",
    "nameerror",
    "keyerror",
    "valueerror",
    "indexerror",
    "validationerror",
    "not found",
    "does not exist",
    "is not defined",
    "no model selected",
    "missing 1 required positional argument",
    "object has no attribute",
)

_EXTERNAL_MARKERS: tuple[str, ...] = (
    "incorrect api key",
    "invalid api key",
    "api key",
    "authenticationerror",
    "authentication",
    "unauthorized",
    "401",
    "403",
    "forbidden",
    "is not set",
    "missing api key",
    "permission denied",
    "connection refused",
    "failed to resolve",
    "max retries exceeded",
    "no such file or directory",
    "could not connect",
    "connection timed out",
    "rate limit",
    "429",
    "too many requests",
    # The selected model isn't callable for this account (the friendly
    # mapping of an OpenAI/Anthropic ``model_not_found`` / "does not have
    # access to model" → "Model not available. Please select a different
    # model."). The agent CANNOT fix this by rebuilding — re-prompting it
    # only burns 3 expensive fix turns (the "stuck on 'Crafting...'" hang)
    # and would either fail again or silently swap the user's chosen model.
    # Treat it as external: caveat once, keep the user's model, no retries.
    "model not available",
    "model_not_found",
    "model is not available",
    "does not have access to model",
    "no access to model",
)


def classify_run_error(message: str | None) -> RunErrorKind:
    """Return the :class:`RunErrorKind` for a verification-run error string.

    Args:
        message: The error text returned by the run engine (may be None).

    Returns:
        FIXABLE for code/wiring/spec bugs, EXTERNAL_RESOURCE when the run
        needs a user-supplied resource, TIMEOUT for run-time-limit hits,
        UNKNOWN for empty or unrecognized errors.
    """
    if not message or not message.strip():
        return RunErrorKind.UNKNOWN

    text = message.casefold()

    if any(marker in text for marker in _TIMEOUT_MARKERS):
        return RunErrorKind.TIMEOUT
    if any(marker in text for marker in _FIXABLE_MARKERS):
        return RunErrorKind.FIXABLE
    if any(marker in text for marker in _EXTERNAL_MARKERS):
        return RunErrorKind.EXTERNAL_RESOURCE
    return RunErrorKind.UNKNOWN
