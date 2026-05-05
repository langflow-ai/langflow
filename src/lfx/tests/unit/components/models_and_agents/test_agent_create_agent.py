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
async def test_should_attach_token_usage_handler_and_set_usage_on_result_properties() -> None:
    """Parity with `LCAgentComponent.run_agent`: TokenUsageCallbackHandler must be wired.

    Legacy behavior at base/agents/agent.py:265-308:
      1. TokenUsageCallbackHandler() is added to callbacks.
      2. After process_agent_events, handler.get_usage() is read.
      3. Usage is set on `self._token_usage` AND `result.properties.usage`.
    Without this, billing/observability that reads `result.properties.usage` breaks.
    """
    from lfx.schema.message import Message as _Msg

    fake_usage = {"input_tokens": 12, "output_tokens": 34, "total_tokens": 46}
    handler_instance = MagicMock()
    handler_instance.get_usage.return_value = fake_usage
    captured_callbacks: list = []

    def _capture_astream(_input_dict, *, config, **_kwargs):
        captured_callbacks.extend(config.get("callbacks") or [])
        return _empty_event_stream()

    fake_graph = MagicMock()
    fake_graph.astream_events = _capture_astream

    component = _build_component()
    component.set_attributes({"input_value": "hi", "chat_history": []})
    final_message = _Msg(text="bye")

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch(
            "lfx.components.models_and_agents.agent.TokenUsageCallbackHandler",
            return_value=handler_instance,
        ),
        patch(
            "lfx.components.models_and_agents.agent.process_agent_events",
            new=AsyncMock(return_value=final_message),
        ),
    ):
        result = await component.run_agent(fake_graph)

    assert handler_instance in captured_callbacks
    assert result.properties.usage == fake_usage
    assert getattr(component, "_token_usage", None) == fake_usage


@pytest.mark.asyncio
async def test_should_update_stored_message_and_send_event_when_token_usage_and_result_has_id() -> None:
    """Parity with legacy lines 304-308: only round-trip the DB when the message was stored.

    A message has an `id` only when emitted to a Chat Output (otherwise `_should_skip_message`
    is True). Skipping this branch means the stored Message in the DB never gets the usage
    field — observability sees an empty `usage` even when tokens were consumed.
    """
    fake_usage = {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12}
    handler_instance = MagicMock()
    handler_instance.get_usage.return_value = fake_usage

    fake_graph = MagicMock()
    fake_graph.astream_events = lambda *_args, **_kwargs: _empty_event_stream()

    initial_result = MagicMock()
    initial_result.get_id.return_value = "msg-stored-123"
    initial_result.properties = MagicMock()
    stored_result = MagicMock()
    stored_result.get_id.return_value = "msg-stored-123"
    stored_result.properties = MagicMock()

    component = _build_component()
    component.set_attributes({"input_value": "hi", "chat_history": []})

    update_stored = AsyncMock(return_value=stored_result)
    send_event = AsyncMock()

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch.object(type(component), "_update_stored_message", new=update_stored),
        patch.object(type(component), "_send_message_event", new=send_event),
        patch(
            "lfx.components.models_and_agents.agent.TokenUsageCallbackHandler",
            return_value=handler_instance,
        ),
        patch(
            "lfx.components.models_and_agents.agent.process_agent_events",
            new=AsyncMock(return_value=initial_result),
        ),
    ):
        result = await component.run_agent(fake_graph)

    update_stored.assert_awaited_once_with(initial_result)
    send_event.assert_awaited_once_with(stored_result)
    assert result is stored_result


@pytest.mark.asyncio
async def test_should_skip_db_round_trip_when_result_has_no_id() -> None:
    """Regression guard: when the Message wasn't stored (no ID) we must NOT hit the DB.

    `_should_skip_message=True` happens when AgentComponent isn't wired to a Chat Output;
    calling `_update_stored_message` on an unstored message would create a phantom row.
    """
    fake_usage = {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}
    handler_instance = MagicMock()
    handler_instance.get_usage.return_value = fake_usage

    fake_graph = MagicMock()
    fake_graph.astream_events = lambda *_args, **_kwargs: _empty_event_stream()

    unstored_result = MagicMock()
    unstored_result.get_id.return_value = None
    unstored_result.properties = MagicMock()

    component = _build_component()
    component.set_attributes({"input_value": "hi", "chat_history": []})

    update_stored = AsyncMock()
    send_event = AsyncMock()

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch.object(type(component), "_update_stored_message", new=update_stored),
        patch.object(type(component), "_send_message_event", new=send_event),
        patch(
            "lfx.components.models_and_agents.agent.TokenUsageCallbackHandler",
            return_value=handler_instance,
        ),
        patch(
            "lfx.components.models_and_agents.agent.process_agent_events",
            new=AsyncMock(return_value=unstored_result),
        ),
    ):
        result = await component.run_agent(fake_graph)

    update_stored.assert_not_awaited()
    send_event.assert_not_awaited()
    # Usage is still set on the in-memory result even when not persisted.
    assert unstored_result.properties.usage == fake_usage
    assert result is unstored_result


@pytest.mark.asyncio
async def test_should_pass_event_manager_on_token_callback_to_process_agent_events() -> None:
    """Parity with legacy lines 261-263, 283: stream tokens to the event manager.

    When the component is wired to an event_manager (typical when running inside the
    Langflow runtime), `process_agent_events` must receive a callback that pipes each
    token chunk to `event_manager.on_token`. Without this, the frontend's live-typing
    view stops working for the AgentComponent.
    """
    captured: dict = {}

    async def _capture_process(stream, _agent_message, _send_message_callback, on_token_callback=None):
        # consume the stream so the adapter doesn't leak
        async for _ in stream:
            pass
        captured["on_token"] = on_token_callback
        return MagicMock(get_id=lambda: None, properties=MagicMock())

    fake_graph = MagicMock()
    fake_graph.astream_events = lambda *_args, **_kwargs: _empty_event_stream()

    on_token_fn = MagicMock(name="event_manager_on_token")
    component = _build_component()
    component.set_attributes({"input_value": "hi", "chat_history": []})
    component._event_manager = MagicMock()
    component._event_manager.on_token = on_token_fn

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch("lfx.components.models_and_agents.agent.process_agent_events", side_effect=_capture_process),
    ):
        await component.run_agent(fake_graph)

    assert captured.get("on_token") is on_token_fn


@pytest.mark.asyncio
async def test_should_pass_none_on_token_callback_when_event_manager_is_absent() -> None:
    """Regression guard: no event_manager → on_token_callback must be None, not a stub."""
    captured: dict = {}

    async def _capture_process(stream, _agent_message, _send_message_callback, on_token_callback=None):
        async for _ in stream:
            pass
        captured["on_token"] = on_token_callback
        return MagicMock(get_id=lambda: None, properties=MagicMock())

    fake_graph = MagicMock()
    fake_graph.astream_events = lambda *_args, **_kwargs: _empty_event_stream()

    component = _build_component()
    component.set_attributes({"input_value": "hi", "chat_history": []})
    component._event_manager = None

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch("lfx.components.models_and_agents.agent.process_agent_events", side_effect=_capture_process),
    ):
        await component.run_agent(fake_graph)

    assert captured.get("on_token") is None


@pytest.mark.asyncio
async def test_should_delete_stored_message_and_emit_remove_event_on_exception_with_message_error() -> None:
    """Parity with legacy lines 285-293: clean up half-stored messages on hard failure.

    When `process_agent_events` raises `ExceptionWithMessageError`, the partial agent
    Message may already exist in the DB. Without cleanup, the orphaned row stays
    visible in the chat history. The legacy run_agent deletes it AND fires a
    `remove_message` event so the frontend drops the stale bubble.
    """
    from lfx.base.agents.events import ExceptionWithMessageError as _ExcWithMsg

    fake_graph = MagicMock()
    fake_graph.astream_events = lambda *_args, **_kwargs: _empty_event_stream()

    # Use a MagicMock for agent_message — Pydantic's Message restricts instance-level
    # method overrides, but ExceptionWithMessageError doesn't enforce the type at runtime.
    half_stored = MagicMock()
    half_stored.get_id.return_value = "msg-half-stored-456"
    raised_exc = _ExcWithMsg(half_stored, "boom")

    component = _build_component()
    component.set_attributes({"input_value": "hi", "chat_history": []})

    delete_message_mock = AsyncMock()
    send_event = AsyncMock()

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch.object(type(component), "_send_message_event", new=send_event),
        patch("lfx.components.models_and_agents.agent.delete_message", new=delete_message_mock),
        patch(
            "lfx.components.models_and_agents.agent.process_agent_events",
            new=AsyncMock(side_effect=raised_exc),
        ),
        pytest.raises(_ExcWithMsg),
    ):
        await component.run_agent(fake_graph)

    delete_message_mock.assert_awaited_once_with(id_="msg-half-stored-456")
    send_event.assert_awaited_once_with(half_stored, category="remove_message")


@pytest.mark.asyncio
async def test_should_skip_delete_message_on_exception_when_message_was_not_stored() -> None:
    """Regression guard: don't call delete_message on a Message with no ID."""
    from lfx.base.agents.events import ExceptionWithMessageError as _ExcWithMsg

    fake_graph = MagicMock()
    fake_graph.astream_events = lambda *_args, **_kwargs: _empty_event_stream()

    unstored = MagicMock()
    unstored.get_id.return_value = None
    raised_exc = _ExcWithMsg(unstored, "boom")

    component = _build_component()
    component.set_attributes({"input_value": "hi", "chat_history": []})

    delete_message_mock = AsyncMock()
    send_event = AsyncMock()

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch.object(type(component), "_send_message_event", new=send_event),
        patch("lfx.components.models_and_agents.agent.delete_message", new=delete_message_mock),
        patch(
            "lfx.components.models_and_agents.agent.process_agent_events",
            new=AsyncMock(side_effect=raised_exc),
        ),
        pytest.raises(_ExcWithMsg),
    ):
        await component.run_agent(fake_graph)

    delete_message_mock.assert_not_awaited()
    # The remove_message event still fires so the frontend drops the partial bubble.
    send_event.assert_awaited_once_with(unstored, category="remove_message")


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
