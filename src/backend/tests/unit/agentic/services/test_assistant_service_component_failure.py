"""Bug #7 (PR-12575): a failed generate_component sub-task must be surfaced honestly.

In a compound turn ("create a component AND build a flow with it") the agent can
fail the ``generate_component`` sub-task and still build a flow with a generic
substitute. Two guarantees, both driven against the REAL streaming generator:

1. The failure is forwarded out-of-band as a ``validation_failed`` progress
   event (so the frontend can react regardless of the agent's prose).
2. Because that progress event is transient (the frontend keeps only the latest
   progress), the FINAL ``complete`` message carries a persistent ``⚠️`` caveat
   — the user is never told a flow is ready while the component they asked for
   was silently dropped.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"

SET_FLOW = {"action": "set_flow", "flow": {"data": {"nodes": [{"id": "Sum-1"}], "edges": []}}}


def _intent(intent: str) -> IntentResult:
    return IntentResult(intent=intent, translation="t")


async def _collect(agen):
    return [e async for e in agen]


def _one_token_stream(**_kw):
    async def gen():
        yield "token", "Working on it..."
        yield "end", {"result": "I built a flow for you."}

    return gen()


def _draining(batches: list[list[dict]]):
    """A drain stub that yields each batch once, then [] forever."""
    queue = list(batches)

    def _drain():
        return queue.pop(0) if queue else []

    return _drain


@pytest.mark.asyncio
async def test_should_yield_validation_failed_when_component_sub_task_fails():
    comp_drain = _draining([[{"error": "Output method 'run' has no return", "class_name": "FooTool"}]])

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("component_then_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=_one_token_stream),
        patch(f"{MODULE}.drain_flow_events", return_value=[]),
        patch(f"{MODULE}.drain_component_events", side_effect=comp_drain),
        patch(f"{MODULE}.reset_working_flow"),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a tool and build a flow with it",
                global_variables={},
                max_retries=1,
            )
        )

    assert any('"step": "validation_failed"' in e and "Output method" in e for e in events)


@pytest.mark.asyncio
async def test_should_append_caveat_to_final_message_when_flow_substitutes_failed_component():
    comp_drain = _draining([[{"error": "ValidationError: Data(data=...) expects a dict"}]])
    flow_drain = _draining([[SET_FLOW]])

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("component_then_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=_one_token_stream),
        patch(f"{MODULE}.drain_flow_events", side_effect=flow_drain),
        patch(f"{MODULE}.drain_component_events", side_effect=comp_drain),
        patch(f"{MODULE}.reset_working_flow"),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a tool and build a flow with it",
                global_variables={},
                max_retries=1,
            )
        )

    complete_events = [e for e in events if '"event": "complete"' in e]
    assert complete_events, events
    blob = "".join(events)
    # The final message admits the component wasn't built (persistent caveat in
    # the completed message), rather than claiming a flow is ready and dropping
    # the component silently. The ⚠️ is JSON-escaped in the SSE stream.
    assert "couldn't create the custom component" in blob
    assert '"component_generation_failed": true' in blob


@pytest.mark.asyncio
async def test_should_not_append_caveat_when_no_component_failed():
    flow_drain = _draining([[SET_FLOW]])

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=_one_token_stream),
        patch(f"{MODULE}.drain_flow_events", side_effect=flow_drain),
        patch(f"{MODULE}.drain_component_events", return_value=[]),
        patch(f"{MODULE}.reset_working_flow"),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build a flow",
                global_variables={},
                max_retries=1,
            )
        )

    blob = "".join(events)
    assert "couldn't create the custom component" not in blob
