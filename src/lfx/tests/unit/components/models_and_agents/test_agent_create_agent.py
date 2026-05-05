"""Tests that AgentComponent uses `langchain.agents.create_agent` (LangGraph) directly.

Per CZL/PLAN_agent_create_agent_only.md, AgentComponent owns its own create_agent path.
It does NOT rely on `LCAgentComponent.run_agent()` or `ToolCallingAgentComponent.create_agent_runnable()`
internally — those code paths still exist for legacy components but are bypassed here.
"""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _empty_event_stream() -> AsyncIterator[dict[str, Any]]:
    if False:
        yield {}  # pragma: no cover — async-generator marker; never runs


async def _from_events(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for event in events:
        yield event


def _build_component():
    """Construct an AgentComponent with minimal attributes for unit testing.

    Patches `_get_llm` so we don't try to resolve a real model provider, and provides
    a predictable LLM placeholder the create_agent mock can identify.
    """
    from lfx.components.models_and_agents.agent import AgentComponent

    component = AgentComponent()
    component._user_id = None
    component.set_attributes(
        {
            "model": "fake-model",
            "api_key": None,
            "tools": [],
            "chat_history": [],
            "input_value": "what's 2+2?",
            "system_prompt": "You are a helpful agent.",
            "max_iterations": 7,
            "handle_parsing_errors": True,
            "verbose": False,
        }
    )
    return component


@pytest.mark.asyncio
async def test_should_call_create_agent_with_resolved_llm_and_tools_when_create_agent_runnable_invoked() -> None:
    fake_llm = MagicMock(name="fake_llm")
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    with (
        patch.object(type(component), "_get_llm", return_value=fake_llm),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    assert captured.get("model") is fake_llm
    assert captured.get("tools") == []
    assert "helpful agent" in (captured.get("system_prompt") or "")


@pytest.mark.asyncio
async def test_should_apply_tool_retry_middleware_when_handle_parsing_errors_set() -> None:
    """`handle_parsing_errors=True` (legacy AgentExecutor knob) maps to ToolRetryMiddleware.

    On AgentExecutor, this prevented hard crashes when an LLM produced output that
    didn't parse as a tool call. On LangGraph the equivalent is a tool-retry middleware.
    Without this wiring, the legacy "Handle Parse Errors" input becomes a silent no-op.
    """
    from langchain.agents.middleware import ToolRetryMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()  # handle_parsing_errors=True
    with (
        patch.object(type(component), "_get_llm", return_value=MagicMock(name="fake_llm")),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert any(isinstance(m, ToolRetryMiddleware) for m in middleware)


@pytest.mark.asyncio
async def test_should_omit_tool_retry_middleware_when_handle_parsing_errors_is_false() -> None:
    """Regression guard: only attach ToolRetryMiddleware when the user opted in."""
    from langchain.agents.middleware import ToolRetryMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    component.set_attributes({"handle_parsing_errors": False})
    with (
        patch.object(type(component), "_get_llm", return_value=MagicMock(name="fake_llm")),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert not any(isinstance(m, ToolRetryMiddleware) for m in middleware)


@pytest.mark.asyncio
async def test_should_return_final_ai_text_when_message_response_runs_end_to_end() -> None:
    """Smoke: full path from message_response → graph → final Message.

    Uses a fake tool-capable chat model that responds with a single AIMessage. The
    test verifies the public API of AgentComponent is preserved: an awaitable
    `message_response()` that returns a Message whose text is the AI's answer.
    """
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage

    class _ToolCapableFakeChat(FakeMessagesListChatModel):
        """Minimal LLM that pretends to support tool binding (no-op)."""

        def bind_tools(self, _tools, **_kwargs):  # type: ignore[override]
            return self

    fake_llm = _ToolCapableFakeChat(responses=[AIMessage(content="The answer is 4.")])
    component = _build_component()
    component.set_attributes({"input_value": "what's 2+2?", "chat_history": []})

    with (
        patch.object(type(component), "_get_llm", return_value=fake_llm),
        patch.object(type(component), "get_agent_requirements", new=AsyncMock(return_value=(fake_llm, [], []))),
        # We don't store / send messages in this isolated unit test.
        patch.object(type(component), "send_message", new=AsyncMock(side_effect=lambda message, **_kw: message)),
    ):
        result = await component.message_response()

    from lfx.schema.message import Message as _Msg

    assert isinstance(result, _Msg)
    assert "answer is 4" in (result.text or "")


@pytest.mark.asyncio
async def test_should_invoke_graph_astream_events_with_messages_input_when_run_agent_called() -> None:
    """`run_agent(graph)` must feed the graph a `{"messages": [...]}` dict.

    LangGraph's `CompiledStateGraph` accepts state-shaped input; this is the contract
    that distinguishes the new path from the legacy `{"input": str, ...}` shape. If
    this assertion regresses, the agent will silently fail or the LLM will see no
    user input.
    """
    from langchain_core.messages import HumanMessage
    from lfx.schema.message import Message

    captured_input: dict = {}

    def _capture_astream(input_dict, **_kwargs):
        captured_input["payload"] = input_dict
        return _empty_event_stream()

    fake_graph = MagicMock()
    fake_graph.astream_events = _capture_astream

    component = _build_component()
    component.set_attributes({"input_value": Message(text="ping", sender="User")})
    fake_result = Message(text="pong")

    with (
        patch("lfx.components.models_and_agents.agent.process_agent_events", new=AsyncMock(return_value=fake_result)),
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
    ):
        result = await component.run_agent(fake_graph)

    assert result is fake_result
    payload = captured_input.get("payload")
    assert isinstance(payload, dict)
    assert "messages" in payload
    assert isinstance(payload["messages"], list)
    # The user's fresh turn must be present as a HumanMessage.
    assert any(isinstance(m, HumanMessage) and "ping" in str(m.content) for m in payload["messages"])


@pytest.mark.asyncio
async def test_should_apply_max_iterations_via_model_call_limit_middleware() -> None:
    """`max_iterations` from the user input maps to ModelCallLimitMiddleware.run_limit.

    LangGraph create_agent has no `max_iterations` param — it expresses the same idea
    via middleware. Without this wiring, the legacy "Max Iterations" input becomes a
    silent no-op.
    """
    from langchain.agents.middleware import ModelCallLimitMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()  # max_iterations=7, handle_parsing_errors=True
    with (
        patch.object(type(component), "_get_llm", return_value=MagicMock(name="fake_llm")),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    limiters = [m for m in middleware if isinstance(m, ModelCallLimitMiddleware)]
    assert limiters, "ModelCallLimitMiddleware must be present when max_iterations is set"
    assert limiters[0].run_limit == 7
