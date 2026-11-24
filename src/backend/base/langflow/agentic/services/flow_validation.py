"""Post-build flow validation loop — Tier-1 static + Tier-2 graph build.

Replaces the rejected "run the whole flow for real + classify" design.
Each attempt is deterministic and zero-LLM-token: ensure every Agent
has a model (auto-assign, never looped on) → Tier-1 static validation →
Tier-2 graph construction (no vertex run). A fixable deterministic
error is fed back to the agent and re-validated, bounded by a hard
attempt cap. A flow that is valid + builds but whose Agent has no
usable model is delivered with an honest caveat. The graph build, the
static validator, the agent-model resolver and the LLM fix are all
injected so this decision logic stays pure and unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from langflow.agentic.services.flow_agent_model import AgentModelOutcome
from langflow.agentic.services.flow_types import MAX_FLOW_VALIDATION_ATTEMPTS

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langflow.agentic.services.flow_graph_build_check import BuildCheckResult
    from langflow.agentic.services.flow_static_validation import FlowValidationReport

# Over-redact rather than ever echo a provider secret in a caveat/log.
_SECRET_RE = re.compile(r"\b(sk|rk|pk|key|token|bearer)[-_ ]?[A-Za-z0-9_\-]{8,}\b", re.IGNORECASE)
_MAX_CAVEAT_CHARS = 300
_MAX_ERRORS_IN_PROMPT = 5


class FlowVerifyStatus(Enum):
    """How the validated flow should be delivered."""

    PASSED = "passed"  # valid + builds — deliver normally
    NEEDS_CAVEAT = "needs_caveat"  # valid + builds, but Agent has no model
    FAILED = "failed"  # deterministic errors, attempts exhausted / no fix


@dataclass(frozen=True)
class FlowVerifyResult:
    """The (possibly fixed) flow plus how to deliver it."""

    status: FlowVerifyStatus
    attempts: int
    caveat: str | None
    flow: dict


def _redact(text: str) -> str:
    scrubbed = _SECRET_RE.sub("***", text or "")
    if len(scrubbed) > _MAX_CAVEAT_CHARS:
        scrubbed = scrubbed[: _MAX_CAVEAT_CHARS - 1].rstrip() + "…"
    return scrubbed


def _summarize(errors: list[str]) -> str:
    return _redact("; ".join(errors[:_MAX_ERRORS_IN_PROMPT]) or "validation failed")


def _no_model_caveat() -> str:
    return (
        "The flow is valid and builds, but its Agent has no language model and no provider "
        "key is configured here — select a model on the Agent to run it."
    )


def _failed_caveat(attempts: int, errors: list[str]) -> str:
    return f"I built the flow but couldn't make it valid after {attempts} attempt(s). Last error: {_summarize(errors)}."


async def verify_flow(
    *,
    flow: dict,
    flow_id: str,
    user_id: str | None,
    agent_model_fn: Callable[[dict], AgentModelOutcome],
    static_fn: Callable[[dict], FlowValidationReport],
    build_fn: Callable[..., Awaitable[BuildCheckResult]],
    fix_fn: Callable[[str], Awaitable[dict | None]],
    max_attempts: int = MAX_FLOW_VALIDATION_ATTEMPTS,
) -> FlowVerifyResult:
    """Validate ``flow``, retrying fixable deterministic errors.

    Args:
        flow: The built working-flow dict.
        flow_id: Flow id, threaded to the Tier-2 graph build.
        user_id: Owning user, threaded to the Tier-2 graph build.
        agent_model_fn: Ensures Agents have a model (deterministic).
        static_fn: Tier-1 static validation.
        build_fn: Tier-2 graph construction (no vertex run).
        fix_fn: Re-prompts the agent; returns a corrected flow or None.
        max_attempts: Hard cost ceiling (only the fix turns cost LLM).

    Returns:
        A :class:`FlowVerifyResult` — never silently broken, never
        looping on the no-model case.
    """
    current = flow
    last_errors = ["unknown error"]
    needs_model_caveat = False
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        needs_model_caveat = agent_model_fn(current) is AgentModelOutcome.NO_PROVIDER

        report = static_fn(current)
        if not report.ok:
            last_errors = report.errors or ["static validation failed"]
        else:
            build = await build_fn(flow=current, flow_id=flow_id, user_id=user_id)
            if build.ok:
                if needs_model_caveat:
                    return FlowVerifyResult(FlowVerifyStatus.NEEDS_CAVEAT, attempt, _no_model_caveat(), current)
                return FlowVerifyResult(FlowVerifyStatus.PASSED, attempt, None, current)
            last_errors = [build.error or "graph build failed"]

        if attempt >= max_attempts:
            break
        fixed = await fix_fn(_summarize(last_errors))
        if not fixed:
            break
        current = fixed

    return FlowVerifyResult(FlowVerifyStatus.FAILED, attempt, _failed_caveat(attempt, last_errors), current)
