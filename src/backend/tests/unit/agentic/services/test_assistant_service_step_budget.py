"""LE-2324: exhausting the step budget must not discard the work already done.

Reproduced live against ``/api/v1/agentic/assist/stream``: on a multi-stage
build the Agent hit LangGraph's ``recursion_limit`` (derived from
``max_iterations * 2 + 5``) after it had already called ``build_flow``. The
stream ended with an ``error`` event and nothing else -- the canvas the agent
had assembled that turn was dropped, so the user could not continue from where
it stopped and had to decompose the request by hand.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"

RECURSION_ERROR = (
    "Error building Component Agent: \n\nRecursion limit of 29 reached without hitting a stop "
    "condition. You can increase the limit by setting the `recursion_limit` config key."
)

PARTIAL_FLOW = {
    "action": "set_flow",
    "flow": {"data": {"nodes": [{"id": "ChatInput-1"}, {"id": "Parser-1"}], "edges": []}},
}


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


async def _run_exhausted_turn():
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=_exhausting_stream),
        # The agent called build_flow AFTER its last token, so the token-loop
        # drain comes back empty and only the error path can still see the work.
        patch(f"{MODULE}.drain_flow_events", side_effect=_draining([[], [PARTIAL_FLOW]])),
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


@pytest.mark.asyncio
async def test_should_tell_the_user_the_partial_flow_was_kept():
    events = await _run_exhausted_turn()

    errors = [json.loads(e.removeprefix("data:").strip()) for e in events if '"event": "error"' in e]
    assert "kept" in errors[-1]["message"].lower(), (
        "on exhaustion with partial work the message must not read as a full stop"
    )
