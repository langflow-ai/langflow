"""WS-1 / RC-1: assistant_service feeds session context to the classifier.

Bug shape (report #1/#3/#4/#8, screenshots 2/3/6/7/8): ``classify_intent``
ran on the bare user text before the canvas summary and conversation
history were known, so a follow-up like "adicione um segundo agente" or
"monte um flow com SumComponent" was classified as question/off_topic and
the agent replied with text instead of acting.

Fix shape: before classifying, the service reads the session's recent
turns + the current-canvas summary, builds a framed disambiguation block
(``build_intent_context``), and forwards it to ``classify_intent`` via the
``context`` kwarg. A fresh session with an empty canvas must still send
``context=None`` (no behavior change).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.conversation_buffer import (
    ConversationBuffer,
    ConversationTurn,
)
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


@pytest.fixture
def fresh_buffer(monkeypatch):
    """Swap the module-level singleton with a fresh, empty buffer."""
    import langflow.agentic.services.conversation_buffer as module

    buf = ConversationBuffer()
    monkeypatch.setattr(module, "_singleton", buf)
    return buf


def _flow_gen():
    async def gen():
        yield "end", {"result": "ok"}

    return gen()


async def _drain(agen):
    return [event async for event in agen]


@pytest.mark.asyncio
async def test_should_pass_session_context_to_classify_intent_when_session_has_prior_turns(fresh_buffer):
    # Arrange — a prior build turn exists for this (user, session).
    fresh_buffer.push(
        "user-1",
        "agentic_s1",
        ConversationTurn(user="create a component that sums a and b", assistant="Done — SumComponent created."),
    )
    mock_classify = AsyncMock(return_value=IntentResult(intent="build_flow", translation="use it"))

    with (
        patch(f"{MODULE}.classify_intent", mock_classify),
        patch(f"{MODULE}.execute_flow_file_streaming", return_value=_flow_gen()),
    ):
        # Act
        await _drain(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="agora monte um flow com o SumComponent",
                global_variables={},
                session_id="agentic_s1",
                user_id="user-1",
            )
        )

    # Assert — the classifier received a context block carrying the prior turn.
    context = mock_classify.call_args[1].get("context")
    assert context is not None, "classify_intent must receive the session context for a follow-up turn"
    assert "create a component that sums a and b" in context


@pytest.mark.asyncio
async def test_should_pass_none_context_to_classify_intent_for_fresh_session(
    fresh_buffer,  # noqa: ARG001 — fixture patches the singleton to an empty buffer
):
    # Arrange — no prior turns, no FLOW_ID → empty canvas. Regression guard:
    # the no-context path must stay byte-identical to today.
    mock_classify = AsyncMock(return_value=IntentResult(intent="question", translation="hi"))

    with (
        patch(f"{MODULE}.classify_intent", mock_classify),
        patch(f"{MODULE}.execute_flow_file_streaming", return_value=_flow_gen()),
    ):
        # Act
        await _drain(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="what is langflow?",
                global_variables={},
                session_id="agentic_fresh",
                user_id="user-1",
            )
        )

    # Assert
    assert mock_classify.call_args[1].get("context") is None


@pytest.mark.asyncio
async def test_should_not_leak_working_flow_when_off_topic_after_canvas_seed(fresh_buffer):  # noqa: ARG001
    """Review regression guard: off_topic must not leak the seeded working flow.

    The WS-1 reorder moved canvas seeding (``_get_current_flow_summary`` →
    ``init_working_flow``) BEFORE the off_topic early-return, which is
    OUTSIDE the try/finally. An off_topic request on a flow with a canvas
    must still leave the working-flow ContextVar clean for the next request
    on this asyncio task.
    """
    from lfx.mcp.flow_builder_tools import get_working_flow, reset_working_flow

    reset_working_flow()

    async def fake_summary(_flow_id, **_kwargs):  # accepts user_id kwarg from production (I2)
        from lfx.mcp.flow_builder_tools import init_working_flow

        init_working_flow({"data": {"nodes": [{"id": "Agent-1"}], "edges": []}}, "flow-1")
        return "nodes: Agent-1"

    off_topic = IntentResult(intent="off_topic", translation="weather?")
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=off_topic),
        patch(f"{MODULE}._get_current_flow_summary", fake_summary),
    ):
        await _drain(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="how is the weather today?",
                global_variables={"FLOW_ID": "flow-1"},
                session_id="agentic_off",
                user_id="user-1",
            )
        )

    assert get_working_flow() is None, (
        "Working flow leaked after an off_topic request — the seeded canvas must be "
        "reset on the off_topic path (it returns before the try/finally)."
    )


@pytest.mark.asyncio
async def test_should_load_current_flow_summary_only_once_per_request(fresh_buffer):  # noqa: ARG001
    # Reordering must not double-read the DB: the canvas summary is computed
    # once and reused for both the intent context and the [Current flow] prefix.
    mock_classify = AsyncMock(return_value=IntentResult(intent="question", translation="hi"))
    summary_calls = 0

    async def fake_summary(_flow_id, **_kwargs):  # accepts user_id kwarg from production (I2)
        nonlocal summary_calls
        summary_calls += 1

    with (
        patch(f"{MODULE}.classify_intent", mock_classify),
        patch(f"{MODULE}.execute_flow_file_streaming", return_value=_flow_gen()),
        patch(f"{MODULE}._get_current_flow_summary", fake_summary),
    ):
        await _drain(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={"FLOW_ID": "abc"},
                session_id="agentic_s2",
                user_id="user-1",
            )
        )

    assert summary_calls == 1, f"_get_current_flow_summary must be called exactly once, got {summary_calls}"
