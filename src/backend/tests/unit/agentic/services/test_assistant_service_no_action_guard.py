"""WS-2 / RC-2: a build/edit request producing no canvas action is not success.

Bug shape (report #1/#4, screenshots 2/6/7/8): intent is build_flow but the
agent only emits text — "Adicionei um segundo agente..." (nothing on the
canvas) or "Deseja que eu faça assim?" (asks to confirm an action the user
already requested). The streaming service used to emit a plain success
``complete`` for that text, so the UI showed it as done.

Fix shape: when ``is_flow_request`` and the run produced ZERO flow updates
(no add/connect/configure/propose_plan/set_flow) and no flow JSON, re-prompt
the agent to actually use its tools; if it still does nothing after the
retries, emit an explicit error instead of a misleading success.

Q&A (``question``) and read-only ``manage_files`` are intentionally NOT
guarded — a text-only answer is legitimate there.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _make_intent(intent: str) -> IntentResult:
    return IntentResult(intent=intent, translation="t")


async def _collect(agen):
    return [e async for e in agen]


@pytest.mark.asyncio
async def test_should_retry_build_flow_when_agent_emits_no_canvas_actions():
    """is_flow_request + zero flow updates → re-prompt instead of fake success."""
    call_count = 0

    def streaming_factory(**_kw):
        nonlocal call_count
        call_count += 1

        async def gen():
            yield "token", "I will add a second agent..."
            yield "end", {"result": "I will add a second agent..."}

        return gen()

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=streaming_factory),
        patch(f"{MODULE}.drain_flow_events", return_value=[]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="adicione um segundo agente",
                global_variables={},
                max_retries=2,
            )
        )

    assert call_count >= 2, f"Expected a corrective retry, executor ran {call_count}x"
    # The run that produced nothing must NOT end in a success complete.
    success = [e for e in events if '"event": "complete"' in e]
    assert not success, f"A no-action build run must not emit a success complete. Events: {events}"
    assert any('"event": "error"' in e for e in events), "Expected an explicit error after no-action retries"


@pytest.mark.asyncio
async def test_should_succeed_build_flow_when_set_flow_emitted():
    """Regression (AC3): a build that DID mutate the canvas still succeeds."""
    flow_gen_calls = 0

    def streaming_factory(**_kw):
        nonlocal flow_gen_calls
        flow_gen_calls += 1

        async def gen():
            yield "end", {"result": "Built it."}

        return gen()

    drain = [[{"action": "set_flow", "flow": {"data": {"nodes": [], "edges": []}}}]] + [[]] * 12

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=streaming_factory),
        patch(f"{MODULE}.drain_flow_events", side_effect=drain),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build a chatbot",
                global_variables={},
                max_retries=2,
            )
        )

    assert flow_gen_calls == 1, "A successful build must not retry"
    assert any('"event": "complete"' in e for e in events)
    assert not any('"event": "error"' in e for e in events)


@pytest.mark.asyncio
async def test_should_not_guard_question_intent_text_only():
    """Regression (AC2): Q&A text-only answers stay successful."""

    def streaming_factory(**_kw):
        async def gen():
            yield "token", "Langflow is a visual framework."
            yield "end", {"result": "Langflow is a visual framework."}

        return gen()

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=streaming_factory),
        patch(f"{MODULE}.drain_flow_events", return_value=[]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="what is langflow?",
                global_variables={},
                max_retries=2,
            )
        )

    assert any('"event": "complete"' in e for e in events), "Q&A must still complete successfully"
    assert not any('"event": "error"' in e for e in events)


@pytest.mark.asyncio
async def test_should_emit_error_not_fake_success_when_no_action_retries_exhausted():
    """Exhausted no-action retries → explicit error, never a 'done' message."""

    def streaming_factory(**_kw):
        async def gen():
            yield "end", {"result": "Adicionei um segundo agente."}

        return gen()

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=streaming_factory),
        patch(f"{MODULE}.drain_flow_events", return_value=[]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="adicione um segundo agente",
                global_variables={},
                max_retries=1,
            )
        )

    assert any('"event": "error"' in e for e in events)
    assert not any('"event": "complete"' in e for e in events)
