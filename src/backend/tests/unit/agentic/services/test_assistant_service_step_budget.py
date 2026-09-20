"""LE-2324: exhausting the step budget must not discard the work already done.

Reproduced live against ``/api/v1/agentic/assist/stream``: on a multi-stage
build the Agent hit LangGraph's ``recursion_limit`` (derived from
``max_iterations * 2 + 5``) after it had already called ``build_flow``. The
stream ended with an ``error`` event and nothing else -- the canvas the agent
had assembled that turn was dropped, so the user could not continue from where
it stopped and had to decompose the request by hand.

Review follow-up (PR #14792): draining is not enough. The rescue must go through
``_reconcile_flow_updates`` like every other drain point -- it is the only place
that strips the internal ``flow_ran`` signal (the canvas has no reducer for it)
and stamps ``auto_apply`` on a ``set_flow``. Yielding raw leaked ``flow_ran`` to
the frontend and let a ``flow_ran``-only batch claim work was kept when nothing
was, and an untagged ``set_flow`` lands as a proposal card that the error branch
of ``assistant-message-body`` never renders.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.helpers.error_handling import (
    PARTIAL_WORK_KEPT_SUFFIX,
    PARTIAL_WORK_PROPOSED_SUFFIX,
)
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"

RECURSION_ERROR = (
    "Error building Component Agent: \n\nRecursion limit of 29 reached without hitting a stop "
    "condition. You can increase the limit by setting the `recursion_limit` config key."
)


def _partial_flow() -> dict:
    """A fresh dict per call: the reconciler stamps ``auto_apply`` in place."""
    return {
        "action": "set_flow",
        "flow": {"data": {"nodes": [{"id": "ChatInput-1"}, {"id": "Parser-1"}], "edges": []}},
    }


def _flow_ran() -> dict:
    return {"action": "flow_ran", "flow_id": "abc"}


def _intent(intent: str) -> IntentResult:
    return IntentResult(intent=intent, translation="t")


async def _collect(agen):
    return [e async for e in agen]


def _exhausting_stream(**_kw):
    """A stream that emits a token, then dies on the step ceiling."""

    async def gen():
        yield "token", "Building the parser stage..."
        msg = RECURSION_ERROR
        raise RuntimeError(msg)
        yield  # pragma: no cover - unreachable, keeps this an async generator

    return gen()


def _draining(batches: list[list[dict]]):
    queue = list(batches)

    def _drain():
        return queue.pop(0) if queue else []

    return _drain


async def _run_exhausted_turn(batches=None):
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=_exhausting_stream),
        # The agent called build_flow AFTER its last token, so the token-loop
        # drain comes back empty and only the error path can still see the work.
        patch(
            f"{MODULE}.drain_flow_events",
            side_effect=_draining(batches if batches is not None else [[], [_partial_flow()]]),
        ),
        patch(f"{MODULE}.drain_component_events", return_value=[]),
        patch(f"{MODULE}.reset_working_flow"),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        return await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build a multi-stage sanitization flow",
                global_variables={},
                max_retries=1,
            )
        )


@pytest.mark.asyncio
async def test_should_emit_the_partial_flow_before_the_step_exhaustion_error():
    events = await _run_exhausted_turn()

    assert any('"event": "flow_update"' in e and "Parser-1" in e for e in events), (
        "the canvas built before the budget ran out was discarded"
    )


@pytest.mark.asyncio
async def test_should_still_report_the_step_exhaustion_error():
    events = await _run_exhausted_turn()

    errors = [json.loads(e.removeprefix("data:").strip()) for e in events if '"event": "error"' in e]
    assert errors, "the user must still be told the budget ran out"
    assert "ran out of steps" in errors[-1]["message"]


def _events_of(events: list[str], kind: str) -> list[dict]:
    parsed = [json.loads(e.removeprefix("data:").strip()) for e in events if f'"event": "{kind}"' in e]
    return [e for e in parsed if (e.get("event") or e.get("type")) == kind]


@pytest.mark.asyncio
async def test_should_not_leak_the_internal_flow_ran_signal():
    """``flow_ran`` is a backend-only signal; the canvas has no reducer for it."""
    events = await _run_exhausted_turn([[], [_flow_ran()]])

    assert _events_of(events, "flow_update") == []


@pytest.mark.asyncio
async def test_should_not_claim_work_was_kept_when_only_flow_ran_was_drained():
    """A drain that carries nothing renderable must not advertise partial work."""
    events = await _run_exhausted_turn([[], [_flow_ran()]])

    message = _events_of(events, "error")[-1]["message"]
    assert PARTIAL_WORK_KEPT_SUFFIX not in message
    assert PARTIAL_WORK_PROPOSED_SUFFIX not in message


@pytest.mark.asyncio
async def test_should_mark_the_partial_flow_for_auto_apply_when_the_agent_already_ran_it():
    """A flow the agent RAN must land on the canvas -- the run already happened."""
    events = await _run_exhausted_turn([[], [_flow_ran(), _partial_flow()]])

    updates = _events_of(events, "flow_update")
    assert updates, "the flow the agent ran was discarded"
    assert updates[-1].get("auto_apply") is True
    assert _events_of(events, "error")[-1]["message"].endswith(PARTIAL_WORK_KEPT_SUFFIX)


@pytest.mark.asyncio
async def test_should_offer_the_partial_flow_for_review_when_it_was_never_run():
    """Without a run the destructive replacement keeps its consent gate."""
    events = await _run_exhausted_turn()

    updates = _events_of(events, "flow_update")
    assert updates, "the partial flow was discarded"
    assert updates[-1].get("auto_apply") is not True, "canvas replaced without consent"
    assert _events_of(events, "error")[-1]["message"].endswith(PARTIAL_WORK_PROPOSED_SUFFIX)
