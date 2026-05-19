"""Derive the user-facing progress step/message for a classified request.

Pure logic extracted from the streaming generator in
``assistant_service`` so the (recurring-bug-prone) label decision —
orchestrating vs plan vs continuation vs neutral — is unit-testable in
isolation and the generator stays focused on streaming.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.agentic.services.flow_types import EDIT_CONTINUATION_INPUT, PLAN_APPROVAL_INPUT
from langflow.agentic.services.helpers.intent_classification import _looks_like_run_request

if TYPE_CHECKING:
    from langflow.agentic.api.schemas import StepType


def decide_progress_step(
    *,
    is_component_request: bool,
    is_document_request: bool,
    is_run_request: bool,
    is_flow_request: bool,
    is_compound: bool,
    original_user_input: str,
) -> tuple[StepType, str]:
    """Return ``(step_name, step_message)`` for the first progress event.

    Precedence mirrors the request router: component → document → run →
    flow → generic. Within a flow request, a multi-step prompt (compound,
    or build_flow that also asks to run) surfaces the dedicated
    ``orchestrating`` indicator; the continuation and plan-approval
    signals get their own labels; everything else is a neutral
    "Working on the flow..." (the real plan card / build tasklist still
    arrives via SSE events — the label must not over-promise "planning").
    """
    if is_component_request:
        return "generating_component", "Generating component..."
    if is_document_request:
        return "generating_document", "Generating document..."
    if is_run_request:
        return "generating", "Running the flow..."
    if is_flow_request:
        stripped = original_user_input.strip()
        is_plan_approval = stripped == PLAN_APPROVAL_INPUT
        is_edit_continuation = stripped == EDIT_CONTINUATION_INPUT
        # A flow request that ALSO asks to run/test in the same prompt is
        # a multi-step orchestration (build → configure → run → report),
        # like the compound pipeline — even for plain build_flow. The run
        # detector here only drives the cosmetic spinner label, never the
        # route, so its language scope is an acceptable trade-off.
        is_build_and_run = (
            not is_plan_approval and not is_edit_continuation and _looks_like_run_request(original_user_input)
        )
        if is_compound or is_build_and_run:
            return "orchestrating", "Orchestrating..."
        if is_edit_continuation:
            return "generating", "Continuing..."
        if is_plan_approval:
            return "generating_flow", "Generating flow..."
        # Fresh build_flow: use the RICH `generating_flow` step so the
        # frontend renders the flow icon/card immediately (parity with
        # `generating_component`) — but keep the message NEUTRAL: at this
        # point the agent may still direct-edit instead of planning, so
        # "Generating plan..." would over-promise. Step != message here.
        return "generating_flow", "Working on the flow..."
    return "generating", "Generating response..."
