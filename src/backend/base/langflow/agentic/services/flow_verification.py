"""Post-build flow verification loop (run → classify → fix → retry).

A built flow is run for real before it is presented to the user. On a
fixable code/wiring/spec error the agent is asked to fix it and it is
re-run, bounded by a hard attempt cap (cost ceiling). On a non-fixable
external-resource error or a timeout the loop stops immediately (no
token burn) and the flow is delivered with an honest caveat instead of
being presented as confidently working. The real graph run and the LLM
fix are injected so this decision logic stays pure and unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from langflow.agentic.services.flow_probe_input import apply_probe_input
from langflow.agentic.services.flow_run_error_classification import (
    RunErrorKind,
    classify_run_error,
)
from langflow.agentic.services.flow_types import MAX_FLOW_VERIFICATION_ATTEMPTS

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

# Tokens that look like provider secrets — never echo them in a caveat or
# log. Conservative on purpose (over-redact rather than leak).
_SECRET_RE = re.compile(r"\b(sk|rk|pk|key|token|bearer)[-_ ]?[A-Za-z0-9_\-]{8,}\b", re.IGNORECASE)
_MAX_CAVEAT_ERROR_CHARS = 300


class FlowVerificationStatus(Enum):
    """Outcome of the verification loop, driving how the flow is delivered."""

    PASSED = "passed"  # ran successfully — present normally
    NEEDS_CAVEAT = "needs_caveat"  # structurally valid, couldn't fully run
    FAILED = "failed"  # fixable errors, attempts exhausted / no fix produced


@dataclass(frozen=True)
class FlowVerificationResult:
    """The verified flow plus how it should be delivered to the user."""

    status: FlowVerificationStatus
    attempts: int
    caveat: str | None
    flow: dict


def _redact(text: str) -> str:
    """Strip secret-looking tokens and cap length for user/agent display."""
    scrubbed = _SECRET_RE.sub("***", text or "")
    if len(scrubbed) > _MAX_CAVEAT_ERROR_CHARS:
        scrubbed = scrubbed[: _MAX_CAVEAT_ERROR_CHARS - 1].rstrip() + "…"
    return scrubbed


def flow_has_loop_edge(flow: dict) -> bool:
    """True when the flow contains a loop feedback edge (an intentional cycle).

    A loop feedback edge targets an ``allows_loop`` output, so its
    ``targetHandle`` is output-shaped (carries ``name`` instead of the normal
    ``fieldName``) — see ``lfx.graph.flow_builder.connect``. Running such a
    cyclic flow to completion for verification is slow and can hang, so the
    caller skips the real run and delivers a structural-only result instead.
    """
    for edge in (flow or {}).get("data", {}).get("edges", []):
        target_handle = (edge.get("data") or {}).get("targetHandle") or {}
        if isinstance(target_handle, dict) and "name" in target_handle and "fieldName" not in target_handle:
            return True
    return False


def loop_skipped_caveat() -> str:
    return (
        "This flow contains a loop, so I built and structurally validated it but "
        "didn't run it here — run it yourself to see the results."
    )


def loop_structural_caveat(issues: list[str]) -> str:
    """Honest, specific caveat for a loop that is structurally incomplete."""
    detail = _redact("; ".join(issues))
    return (
        "This flow contains a loop, so I validated its structure instead of running it, "
        f"and it looks incomplete: {detail} Connect those inputs, then run it."
    )


async def verify_loop_structure(
    *,
    flow: dict,
    validate_fn: Callable[[dict], list[str]],
    fix_fn: Callable[[str], Awaitable[dict | None]],
    max_attempts: int = MAX_FLOW_VERIFICATION_ATTEMPTS,
) -> FlowVerificationResult:
    """Validate a cyclic flow's structure (no execution), retrying fixable gaps.

    A loop can't be run to completion safely, so instead of executing it we
    check its wiring. On failure the agent is asked to repair the exact
    missing connections and the flow is re-validated, bounded by
    ``max_attempts`` fix turns. A structurally sound loop is delivered as
    ready; one still incomplete after the cap is delivered with an explicit
    "incomplete — connect X" caveat, never as a confident success.
    """
    current = flow
    issues = validate_fn(current)
    attempt = 0
    while issues and attempt < max_attempts:
        attempt += 1
        fixed = await fix_fn("; ".join(issues))
        if not fixed:
            break
        current = fixed
        issues = validate_fn(current)

    if not issues:
        return FlowVerificationResult(FlowVerificationStatus.PASSED, attempt, None, current)
    return FlowVerificationResult(FlowVerificationStatus.NEEDS_CAVEAT, attempt, loop_structural_caveat(issues), current)


def _external_caveat(error: str) -> str:
    return (
        "I built the flow and it's structurally valid, but I couldn't fully run it here "
        f"because: {_redact(error)}. It should work once that is available on your side."
    )


def _failed_caveat(attempts: int, error: str) -> str:
    return f"I built the flow but couldn't get it to run after {attempts} attempt(s). Last error: {_redact(error)}."


async def verify_built_flow(
    *,
    flow: dict,
    run_fn: Callable[[dict], Awaitable[dict]],
    fix_fn: Callable[[str], Awaitable[dict | None]],
    max_attempts: int = MAX_FLOW_VERIFICATION_ATTEMPTS,
) -> FlowVerificationResult:
    """Run the flow, retrying fixable failures up to ``max_attempts``.

    Args:
        flow: The built working-flow dict.
        run_fn: Executes a flow, returns ``{"result", "metrics"}`` on
            success or ``{"error": msg}`` on failure.
        fix_fn: Given the error message, returns a corrected flow dict
            (or ``None`` when the agent cannot produce a fix).
        max_attempts: Hard cap on real runs (cost ceiling).

    Returns:
        A :class:`FlowVerificationResult` describing how to deliver the
        (possibly fixed) flow — never silently broken.
    """
    current = flow
    last_error = "unknown error"
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        apply_probe_input(current)
        result = await run_fn(current)
        if "error" not in result:
            return FlowVerificationResult(FlowVerificationStatus.PASSED, attempt, None, current)

        last_error = result.get("error") or "unknown error"
        kind = classify_run_error(last_error)
        if kind in (RunErrorKind.EXTERNAL_RESOURCE, RunErrorKind.TIMEOUT):
            return FlowVerificationResult(
                FlowVerificationStatus.NEEDS_CAVEAT, attempt, _external_caveat(last_error), current
            )

        if attempt >= max_attempts:
            break
        fixed = await fix_fn(last_error)
        if not fixed:
            break
        current = fixed

    return FlowVerificationResult(FlowVerificationStatus.FAILED, attempt, _failed_caveat(attempt, last_error), current)
