"""Tests that AgentComponent uses `langchain.agents.create_agent` (LangGraph) directly.

Per CZL/PLAN_agent_create_agent_only.md, AgentComponent owns its own create_agent path.
It does NOT rely on `LCAgentComponent.run_agent()` or `ToolCallingAgentComponent.create_agent_runnable()`
internally — those code paths still exist for legacy components but are bypassed here.
"""

import os
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.graph.state import CompiledStateGraph


async def _empty_event_stream() -> AsyncIterator[dict[str, Any]]:
    if False:
        yield {}  # pragma: no cover — async-generator marker; never runs


async def _from_events(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for event in events:
        yield event


def _fake_graph(astream_events_impl):
    """Build a MagicMock that passes `isinstance(_, CompiledStateGraph)` and exposes astream_events."""
    graph = MagicMock(spec=CompiledStateGraph)
    graph.astream_events = astream_events_impl
    return graph


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

    Note: ToolRetryMiddleware is only wired when tools are actually present — see
    `test_should_skip_tool_retry_middleware_when_no_tools_attached` (UI-003 latency).
    """
    from langchain.agents.middleware import ToolRetryMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()  # handle_parsing_errors=True
    component.set_attributes({"tools": [MagicMock(name="some_tool")]})
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
async def test_should_use_create_agent_for_all_providers_including_watsonx() -> None:
    """All LLM providers go through `langchain.agents.create_agent` natively.

    Earlier versions had a WatsonX-specific fallback to the legacy `create_granite_agent`,
    but that hardcoded `tool_choice='required'` which the WatsonX API now rejects.
    Removed because `ChatWatsonx.bind_tools` works correctly with create_agent.
    """
    fake_watsonx = MagicMock(name="ChatWatsonx_fake")
    type(fake_watsonx).__name__ = "ChatWatsonx"

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    with (
        patch.object(type(component), "_get_llm", return_value=fake_watsonx),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    assert captured.get("model") is fake_watsonx, "WatsonX must reach create_agent natively"


@pytest.mark.asyncio
async def test_should_attach_single_tool_call_middleware_when_llm_is_watsonx() -> None:
    """Attach SingleToolCallMiddleware when the LLM is WatsonX.

    WatsonX rejects multi-tool-call assistant turns with:
    "This model only supports single tool-calls at once!"

    To keep WatsonX flows working with the new create_agent path, attach the
    `SingleToolCallMiddleware` (clamps multi-call responses to one). Other
    providers (OpenAI, Anthropic, etc.) emit multi-tool-calls happily, so the
    middleware is gated on WatsonX detection only.
    """
    from lfx.components.models_and_agents.agent_helpers.single_tool_call_middleware import (
        SingleToolCallMiddleware,
    )

    fake_watsonx = MagicMock(name="ChatWatsonx_fake")
    type(fake_watsonx).__name__ = "ChatWatsonx"

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    with (
        patch.object(type(component), "_get_llm", return_value=fake_watsonx),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert any(isinstance(m, SingleToolCallMiddleware) for m in middleware), (
        "WatsonX must get SingleToolCallMiddleware to clamp multi-tool-call responses"
    )


@pytest.mark.asyncio
async def test_should_not_attach_single_tool_call_middleware_for_non_watsonx_providers() -> None:
    """Do not attach SingleToolCallMiddleware for non-WatsonX providers.

    OpenAI/Anthropic models handle multi-tool-calls fine. Attaching the clamp
    would needlessly serialize their parallel tool calls and slow them down.
    """
    from lfx.components.models_and_agents.agent_helpers.single_tool_call_middleware import (
        SingleToolCallMiddleware,
    )

    fake_openai = MagicMock(name="ChatOpenAI_fake")
    type(fake_openai).__name__ = "ChatOpenAI"

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    with (
        patch.object(type(component), "_get_llm", return_value=fake_openai),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert not any(isinstance(m, SingleToolCallMiddleware) for m in middleware)


@pytest.mark.asyncio
async def test_should_attach_watsonx_placeholder_middleware_when_llm_is_watsonx() -> None:
    """Attach WatsonXPlaceholderMiddleware when the LLM is WatsonX.

    WatsonX models occasionally emit literal placeholder strings (e.g.
    `<result-from-search>`) in tool call args instead of real values. The
    middleware re-invokes the model once with a corrective SystemMessage so
    the agent loop recovers instead of running the tool with garbage.
    """
    from lfx.components.models_and_agents.agent_helpers.placeholder_corrective_middleware import (
        WatsonXPlaceholderMiddleware,
    )

    fake_watsonx = MagicMock(name="ChatWatsonx_fake")
    type(fake_watsonx).__name__ = "ChatWatsonx"

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    with (
        patch.object(type(component), "_get_llm", return_value=fake_watsonx),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert any(isinstance(m, WatsonXPlaceholderMiddleware) for m in middleware), (
        "WatsonX must get WatsonXPlaceholderMiddleware to recover from placeholder tool args"
    )


@pytest.mark.asyncio
async def test_should_not_attach_watsonx_placeholder_middleware_for_non_watsonx_providers() -> None:
    """Don't pay the placeholder-detection cost on providers that don't have this quirk."""
    from lfx.components.models_and_agents.agent_helpers.placeholder_corrective_middleware import (
        WatsonXPlaceholderMiddleware,
    )

    fake_openai = MagicMock(name="ChatOpenAI_fake")
    type(fake_openai).__name__ = "ChatOpenAI"

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    with (
        patch.object(type(component), "_get_llm", return_value=fake_openai),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert not any(isinstance(m, WatsonXPlaceholderMiddleware) for m in middleware)


@pytest.mark.asyncio
async def test_should_order_single_tool_call_middleware_outside_watsonx_placeholder_middleware() -> None:
    """SingleToolCallMiddleware must wrap WatsonXPlaceholderMiddleware.

    The clamp is applied to the final response — including any corrective
    re-invoke. Per langchain's middleware composition, the first item in the
    list is the outermost layer.
    """
    from lfx.components.models_and_agents.agent_helpers.placeholder_corrective_middleware import (
        WatsonXPlaceholderMiddleware,
    )
    from lfx.components.models_and_agents.agent_helpers.single_tool_call_middleware import (
        SingleToolCallMiddleware,
    )

    fake_watsonx = MagicMock(name="ChatWatsonx_fake")
    type(fake_watsonx).__name__ = "ChatWatsonx"

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    with (
        patch.object(type(component), "_get_llm", return_value=fake_watsonx),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    single_idx = next(i for i, m in enumerate(middleware) if isinstance(m, SingleToolCallMiddleware))
    placeholder_idx = next(i for i, m in enumerate(middleware) if isinstance(m, WatsonXPlaceholderMiddleware))
    assert single_idx < placeholder_idx, (
        "SingleToolCallMiddleware must come before WatsonXPlaceholderMiddleware (outermost wraps innermost)"
    )


@pytest.mark.asyncio
async def test_should_yield_clean_single_tool_call_when_watsonx_response_has_placeholders_and_multiple_tools() -> None:
    """End-state composition test: verifies BEHAVIOR, not list-index ordering.

    A future refactor that flips both the list ordering AND langchain's composition
    convention would pass the index-based test but break the contract. This test
    feeds a response that needs BOTH protections (placeholders + multi tool-calls)
    through the real middleware chain and asserts the final state: one tool call,
    no placeholders, no leakage of the corrective re-invoke into the user-visible
    output.
    """
    from langchain.agents.middleware import ModelResponse
    from langchain_core.messages import AIMessage
    from lfx.components.models_and_agents.agent_helpers.placeholder_corrective_middleware import (
        WatsonXPlaceholderMiddleware,
    )
    from lfx.components.models_and_agents.agent_helpers.single_tool_call_middleware import (
        SingleToolCallMiddleware,
    )

    placeholder_call = {
        "id": "call_1",
        "name": "search",
        "args": {"query": "<result-from-previous-search>"},
        "type": "tool_call",
    }
    extra_call_one = {"id": "call_2", "name": "fetch", "args": {"url": "https://x"}, "type": "tool_call"}
    extra_call_two = {"id": "call_3", "name": "calc", "args": {"expr": "1+1"}, "type": "tool_call"}

    # First handler call: response with placeholder + 3 tool calls (worst-case
    # watsonx response). Second call (corrective re-invoke): same multi-call shape
    # but placeholders cleaned up.
    bad = ModelResponse(result=[AIMessage(content="", tool_calls=[placeholder_call, extra_call_one, extra_call_two])])
    cleaned = ModelResponse(
        result=[
            AIMessage(
                content="",
                tool_calls=[
                    {**placeholder_call, "args": {"query": "real value"}},
                    extra_call_one,
                    extra_call_two,
                ],
            )
        ]
    )
    handler_calls: list = []

    def model_call(request):
        handler_calls.append(request)
        return cleaned if len(handler_calls) > 1 else bad

    # Compose as `_build_middleware` produces: SingleToolCall outermost,
    # WatsonXPlaceholder innermost. Outer wraps inner wraps the raw model call.
    placeholder_mw = WatsonXPlaceholderMiddleware()
    single_mw = SingleToolCallMiddleware()

    def _override(**kw):
        return SimpleNamespace(messages=kw["messages"], override=lambda **_kw: None)

    request = SimpleNamespace(messages=[], override=_override)

    def inner_wrapped(req):
        return placeholder_mw.wrap_model_call(req, model_call)

    final = single_mw.wrap_model_call(request, inner_wrapped)

    final_msg = final.result[0]
    assert len(final_msg.tool_calls) == 1, "SingleToolCall must clamp to one"
    assert final_msg.tool_calls[0]["args"] == {"query": "real value"}, "placeholder must be replaced before clamp"
    # Sanity: corrective re-invoke happened exactly once.
    assert len(handler_calls) == 2


@pytest.mark.asyncio
async def test_should_recover_when_llm_emits_malformed_tool_args() -> None:
    """Pydantic ValidationError from bad tool args must NOT crash the agent build.

    Small/local models (Ollama, llama, etc.) often emit malformed tool calls — e.g.
    a string `"http://x"` for a parameter typed `list[str]`. The agent must recover
    via `ToolRetryMiddleware` (default `retry_on=(Exception,)`, `on_failure='continue'`)
    so the LLM sees the error and can correct on retry, rather than crashing the
    whole component build.
    """
    from langchain.agents.middleware import ToolRetryMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()  # handle_parsing_errors=True
    component.set_attributes({"tools": [MagicMock(name="some_tool")]})
    with (
        patch.object(type(component), "_get_llm", return_value=MagicMock(name="fake_llm")),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    retry = next((m for m in middleware if isinstance(m, ToolRetryMiddleware)), None)
    assert retry is not None, "ToolRetryMiddleware must be wired when handle_parsing_errors=True"
    # Defaults: retry_on=(Exception,), on_failure='continue'.
    # Both are required for recovery from Pydantic ValidationError on tool args.
    assert Exception in retry.retry_on, "Must retry on Exception (covers ValidationError)"
    assert retry.on_failure == "continue", "Must convert exhausted retries into a retry-message, not crash"


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

    fake_graph = MagicMock(spec=CompiledStateGraph)
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

    fake_graph = MagicMock(spec=CompiledStateGraph)
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

    fake_graph = MagicMock(spec=CompiledStateGraph)
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

    fake_graph = MagicMock(spec=CompiledStateGraph)
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

    fake_graph = MagicMock(spec=CompiledStateGraph)
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

    fake_graph = MagicMock(spec=CompiledStateGraph)
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

    fake_graph = MagicMock(spec=CompiledStateGraph)
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
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI API key required")
async def test_should_call_tool_and_populate_token_usage_when_running_against_real_openai_model() -> None:
    """Drives `message_response()` end-to-end against a real model with one tool attached.

    Validates the bind_tools → create_agent → graph → token callback →
    result.properties.usage chain in a single shot — fakes can't validate
    streaming order, real bind_tools, or the token callback wiring at the
    same time.

    Skipped without `OPENAI_API_KEY`; uses `gpt-4o-mini` to keep the run cheap.
    """
    from langchain_core.tools import tool

    langchain_openai = pytest.importorskip("langchain_openai")

    @tool
    def echo(text: str) -> str:
        """Echo the given text back verbatim."""
        return text

    llm = langchain_openai.ChatOpenAI(model="gpt-4o-mini", temperature=0)

    component = _build_component()
    component.set_attributes(
        {
            "input_value": "Use the echo tool to echo the literal word 'pong', then tell me what it returned.",
            "chat_history": [],
        }
    )

    with (
        patch.object(type(component), "_get_llm", return_value=llm),
        patch.object(type(component), "get_agent_requirements", new=AsyncMock(return_value=(llm, [echo], []))),
        patch.object(type(component), "send_message", new=AsyncMock(side_effect=lambda message, **_kw: message)),
    ):
        result = await component.message_response()

    from lfx.schema.message import Message as _Msg

    assert isinstance(result, _Msg)
    # Token usage was populated by TokenUsageCallbackHandler on a real call.
    usage = getattr(getattr(result, "properties", None), "usage", None)
    assert usage is not None, "result.properties.usage must be populated for billing/observability"
    assert (usage.get("input_tokens") or 0) > 0, "input_tokens must be reported by the real model"


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI API key required")
async def test_should_stream_multiple_token_chunks_to_event_manager_when_running_against_real_openai_model() -> None:
    """E2E proof that the streaming pipeline works against a real OpenAI model.

    Hard-coding ``stream=True`` in ``_get_llm`` is only useful if the pipeline that
    consumes those chunks (``astream_events(v2)`` → ``handle_on_chain_stream`` →
    ``event_manager.on_token``) is intact. This test exercises the full chain against
    a real model and asserts that multiple token callbacks fire — meaning real
    token-by-token streaming, not a single bulk delivery.

    A failure here would indicate either: (a) the underlying chat model is not built
    with ``streaming=True``, or (b) ``handle_on_chain_stream`` stopped forwarding
    ``on_chat_model_stream`` chunks to the event manager.
    """
    langchain_openai = pytest.importorskip("langchain_openai")

    llm = langchain_openai.ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        streaming=True,
        stream_usage=True,
    )

    component = _build_component()
    component.set_attributes(
        {
            "input_value": "Count from 1 to 8 in English, one number per line.",
            "chat_history": [],
        }
    )

    token_chunks: list[str] = []

    def _on_token(*, data):
        chunk = data.get("chunk")
        if chunk:
            token_chunks.append(chunk)

    component._event_manager = SimpleNamespace(
        on_token=_on_token,
        on_message=lambda **_kw: None,
        on_remove_message=lambda **_kw: None,
    )

    # Simulate the production send_message callback: it stores the message and
    # assigns an ID. handle_on_chain_stream short-circuits when ``message_id`` is
    # falsy, so without this the streaming path never fires the on_token callback.
    async def _send_message_with_id(message, **_kw):
        if not message.get_id():
            message.id = "stub-message-id"
        return message

    with (
        patch.object(type(component), "_get_llm", return_value=llm),
        patch.object(type(component), "get_agent_requirements", new=AsyncMock(return_value=(llm, [], []))),
        patch.object(type(component), "send_message", new=AsyncMock(side_effect=_send_message_with_id)),
    ):
        result = await component.message_response()

    from lfx.schema.message import Message as _Msg

    assert isinstance(result, _Msg)
    assert (result.text or "").strip(), "real model must return some text"
    assert len(token_chunks) > 1, (
        f"Expected multiple streamed token chunks; got {len(token_chunks)} chunk(s). "
        "When ChatOpenAI is instantiated with streaming=False, LangGraph delivers the "
        "response in a single on_chat_model_end event and on_token never fires — the "
        "Playground's live-typing UX is silently disabled in that case."
    )


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

    fake_graph = MagicMock(spec=CompiledStateGraph)
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


# ===== Eager bind_tools validation ============================================


@pytest.mark.asyncio
async def test_should_raise_at_build_time_when_llm_does_not_support_tool_calling() -> None:
    """Tool-incapable models must fail at flow-build time, not at runtime.

    `langchain.agents.create_agent` is lazy about validating `bind_tools` support.
    Without an explicit eager check, an LLM that doesn't support tool calling
    builds the graph fine and only fails on the first user message — much worse
    UX than a clear error in the canvas. The legacy `create_tool_calling_agent`
    raised `NotImplementedError` at build time; we preserve that contract.
    """
    bad_llm = MagicMock(name="bad_llm")
    bad_llm.bind_tools.side_effect = NotImplementedError("provider doesn't support bind_tools")

    component = _build_component()
    component.set_attributes({"tools": [MagicMock(name="some_tool")]})

    with (
        patch.object(type(component), "_get_llm", return_value=bad_llm),
        pytest.raises(NotImplementedError, match="does not support tool calling"),
    ):
        component.create_agent_runnable()


@pytest.mark.asyncio
async def test_should_pass_through_other_bind_tools_exceptions_unchanged() -> None:
    """Only the documented "no tool calling" exceptions are mapped to the user-facing message.

    `ValueError` from a misconfigured tool, for example, should propagate untouched
    so it surfaces its real cause in the logs.
    """
    bad_llm = MagicMock(name="bad_llm")
    bad_llm.bind_tools.side_effect = ValueError("tool x is missing arg schema")

    component = _build_component()
    component.set_attributes({"tools": [MagicMock(name="some_tool")]})

    with (
        patch.object(type(component), "_get_llm", return_value=bad_llm),
        pytest.raises(ValueError, match="missing arg schema"),
    ):
        component.create_agent_runnable()


@pytest.mark.asyncio
async def test_should_skip_eager_bind_tools_validation_when_no_tools_attached() -> None:
    """An Agent without tools doesn't need a tool-calling capable model.

    Forcing `bind_tools(...)` on a no-tools flow would shut out plain chat models
    (which legitimately don't implement bind_tools), so the eager validation is
    gated behind a non-empty tools list.
    """
    chat_only_llm = MagicMock(name="chat_only")
    chat_only_llm.bind_tools.side_effect = NotImplementedError("no bind_tools support")

    component = _build_component()
    component.set_attributes({"tools": []})

    with (
        patch.object(type(component), "_get_llm", return_value=chat_only_llm),
        patch("lfx.components.models_and_agents.agent.create_agent", return_value=MagicMock()),
    ):
        # Must not raise — validation skipped because tools is empty.
        component.create_agent_runnable()

    chat_only_llm.bind_tools.assert_not_called()


@pytest.mark.asyncio
async def test_should_map_attribute_error_from_bind_tools_to_user_message() -> None:
    """Some providers don't expose `bind_tools` at all (raises AttributeError)."""
    bad_llm = MagicMock(name="bad_llm")
    bad_llm.bind_tools.side_effect = AttributeError("'X' object has no attribute 'bind_tools'")

    component = _build_component()
    component.set_attributes({"tools": [MagicMock(name="some_tool")]})

    with (
        patch.object(type(component), "_get_llm", return_value=bad_llm),
        pytest.raises(NotImplementedError, match="does not support tool calling"),
    ):
        component.create_agent_runnable()


@pytest.mark.asyncio
async def test_should_map_type_error_from_bind_tools_to_user_message() -> None:
    """Some providers raise TypeError on signature mismatches; same UX failure."""
    bad_llm = MagicMock(name="bad_llm")
    bad_llm.bind_tools.side_effect = TypeError("bind_tools() got unexpected kwarg")

    component = _build_component()
    component.set_attributes({"tools": [MagicMock(name="some_tool")]})

    with (
        patch.object(type(component), "_get_llm", return_value=bad_llm),
        pytest.raises(NotImplementedError, match="does not support tool calling"),
    ):
        component.create_agent_runnable()


# ===== Input info-text overrides ==============================================


@pytest.mark.asyncio
async def test_should_not_mutate_shared_base_inputs_when_overriding_info_text() -> None:
    """`_agent_base_inputs()` substitutes new instances; it must not edit the shared list.

    `LCToolsAgentComponent.get_base_inputs()` returns the same list object every call
    (via the `_base_inputs` class attribute). Mutating those instances would leak the
    AgentComponent-specific info text into every other LCAgentComponent subclass.
    """
    from lfx.base.agents.agent import LCToolsAgentComponent
    from lfx.components.models_and_agents.agent import _agent_base_inputs

    pristine_before = {inp.name: inp.info for inp in LCToolsAgentComponent.get_base_inputs()}

    customized = _agent_base_inputs()
    customized_info = {inp.name: inp.info for inp in customized}
    # The override actually changed the info text on the customized copy.
    assert customized_info["handle_parsing_errors"] != pristine_before["handle_parsing_errors"]
    assert customized_info["max_iterations"] != pristine_before["max_iterations"]

    pristine_after = {inp.name: inp.info for inp in LCToolsAgentComponent.get_base_inputs()}
    assert pristine_after == pristine_before, (
        "AgentComponent's input overrides leaked into the shared LCToolsAgentComponent base list"
    )


@pytest.mark.asyncio
async def test_should_drop_verbose_input_from_agent_component() -> None:
    """`verbose` is a no-op on the create_agent path and must be removed from the schema.

    The legacy AgentExecutor honored `verbose=True` by dumping reasoning steps to
    stdout. Under create_agent, every step is already surfaced via the "Agent Steps"
    content blocks in the chat panel — `verbose` has nothing to toggle. Keeping a
    deprecated boolean in the input schema would just confuse users, so we drop it
    entirely. Saved flows that carry a `verbose` value ignore it on load.
    """
    from lfx.base.agents.agent import LCToolsAgentComponent
    from lfx.components.models_and_agents.agent import AgentComponent, _agent_base_inputs

    # Sanity check: the parent class still declares verbose (we're scoping the
    # removal to AgentComponent, not yanking it from every LCAgentComponent subclass).
    parent_input_names = {inp.name for inp in LCToolsAgentComponent.get_base_inputs()}
    assert "verbose" in parent_input_names, "test premise broken — base class no longer declares verbose"

    # `_agent_base_inputs()` filters it out.
    customized_names = {inp.name for inp in _agent_base_inputs()}
    assert "verbose" not in customized_names

    # The full AgentComponent inputs list also lacks verbose.
    component_input_names = {inp.name for inp in AgentComponent.inputs}
    assert "verbose" not in component_input_names


@pytest.mark.asyncio
async def test_should_not_require_verbose_in_update_build_config() -> None:
    """`update_build_config` must not require `verbose` after the input was dropped.

    Regression: when the user changes the model in the canvas, the FE re-sends
    the build_config. After dropping `verbose` from the input set, that
    build_config no longer carries the key, and the legacy required-keys check
    raised ``Missing required keys in build_config: ['verbose']`` on every
    model change. The validator must accept a build_config without `verbose`.
    """
    component = _build_component()

    # Build a build_config that has every key the validator requires *except* verbose.
    from lfx.schema.dotdict import dotdict

    build_config = dotdict(
        {
            "code": {"value": ""},
            "_type": {"value": "AgentComponent"},
            "model": {"value": "fake-model"},
            "tools": {"value": []},
            "input_value": {"value": ""},
            "add_current_date_tool": {"value": False},
            "add_calculator_tool": {"value": False},
            "system_prompt": {"value": ""},
            "agent_description": {"value": ""},
            "max_iterations": {"value": 15},
            "handle_parsing_errors": {"value": True},
        }
    )

    # Patch the helpers that touch the network / option cache so we isolate
    # the validator branch.
    with (
        patch(
            "lfx.components.models_and_agents.agent.handle_model_input_update",
            side_effect=lambda **kwargs: kwargs["build_config"],
        ),
        patch.object(type(component), "update_input_types", side_effect=lambda bc: bc),
    ):
        # Should NOT raise. If it does, the canvas surfaces "Error while updating
        # the Component — Missing required keys in build_config: ['verbose']".
        await component.update_build_config(build_config, [], field_name="model")


# ===== _inject_dynamic_prompt_values: connected (Message) system_prompt =========
# CodeRabbit PR #12992 (comment 3266521738): `system_prompt` is a MultilineInput
# that accepts connections (e.g. a Prompt node in Invoice Summarizer wires into
# Agent.system_prompt). When the connected value arrives as a Message, the old
# `prompt.replace(...)` raised AttributeError before the agent could run.


def test_should_replace_placeholders_when_system_prompt_arrives_as_a_message() -> None:
    """A connected `Message` system_prompt must be normalized to text, not crash.

    `_inject_dynamic_prompt_values` did `prompt.replace(...)` directly; a Message has
    no `.replace`, so a connected Prompt node blew up the agent build with
    AttributeError. The helper must reuse `_extract_text_content` first.
    """
    from lfx.schema.message import Message

    component = _build_component()
    with patch.object(type(component), "_get_resolved_model_name", return_value="gpt-test"):
        result = component._inject_dynamic_prompt_values(Message(text="Model {model_name} on {current_date}."))

    assert isinstance(result, str)
    assert "{model_name}" not in result
    assert "gpt-test" in result
    assert "{current_date}" not in result


def test_should_return_none_when_system_prompt_is_none() -> None:
    """Preserve the original contract: None in → None out (callers rely on `or ''`)."""
    component = _build_component()

    assert component._inject_dynamic_prompt_values(None) is None


def test_should_still_replace_placeholders_when_system_prompt_is_plain_string() -> None:
    """Regression guard: the plain-string path must keep working unchanged."""
    component = _build_component()
    with patch.object(type(component), "_get_resolved_model_name", return_value="m1"):
        result = component._inject_dynamic_prompt_values("hello {model_name}")

    assert result == "hello m1"


# ===== max_iterations must never silently disable the call cap =================
# CodeRabbit PR #12992 (comment 3266521785): `if max_iterations:` treats a saved
# `0` as "no limit", removing the ModelCallLimitMiddleware guard entirely and
# allowing unbounded model/tool calls (DoS-via-loop).


@pytest.mark.asyncio
async def test_should_still_cap_model_calls_when_max_iterations_is_zero() -> None:
    """A saved `max_iterations=0` must NOT remove the iteration cap.

    `0` is falsy, so `if max_iterations:` skipped ModelCallLimitMiddleware and the
    agent could loop unbounded. A non-positive value must be clamped to a real cap.
    """
    from langchain.agents.middleware import ModelCallLimitMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    component.set_attributes({"max_iterations": 0})
    with (
        patch.object(type(component), "_get_llm", return_value=MagicMock(name="fake_llm")),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    limiters = [m for m in middleware if isinstance(m, ModelCallLimitMiddleware)]
    assert limiters, "ModelCallLimitMiddleware must remain when max_iterations is 0 (no unbounded loop)"
    assert limiters[0].run_limit >= 1


@pytest.mark.asyncio
async def test_should_skip_tool_retry_middleware_when_no_tools_attached() -> None:
    """Trivial-prompt latency guard (QA UI-003).

    `ToolRetryMiddleware` exists to recover from runtime errors in tool execution.
    With an empty tools list it has nothing to retry, but its presence still
    inflates the compiled graph and adds per-invocation middleware overhead on
    every model call. For "Say hello"-style prompts (no tools, gpt-4o-mini) the
    baseline expectation is 1-2s wall and we currently observe 4.8-14.2s. The
    middleware audit is one cheap, low-risk improvement: don't wire what can't
    fire.
    """
    from langchain.agents.middleware import ToolRetryMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="compiled_state_graph")

    component = _build_component()
    component.set_attributes({"tools": [], "handle_parsing_errors": True})
    with (
        patch.object(type(component), "_get_llm", return_value=MagicMock(name="fake_llm")),
        patch("lfx.components.models_and_agents.agent.create_agent", side_effect=_capture_create_agent),
    ):
        component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert not any(isinstance(m, ToolRetryMiddleware) for m in middleware), (
        "ToolRetryMiddleware must NOT be attached when there are no tools — it cannot fire and only "
        "adds per-call middleware overhead, contributing to the UI-003 trivial-prompt latency."
    )


def test_should_declare_min_one_range_spec_on_max_iterations_input() -> None:
    """The UI must not let users set `max_iterations` below 1."""
    from lfx.components.models_and_agents.agent import _agent_base_inputs

    max_iter = next(inp for inp in _agent_base_inputs() if inp.name == "max_iterations")

    assert max_iter.range_spec is not None, "max_iterations needs a RangeSpec to block sub-1 values"
    assert max_iter.range_spec.min == 1


# ===== recursion_limit must be tied to max_iterations =========================
# QA UI-009/UI-010 (PR #12992): malformed prompts loop on tool calls until
# LangGraph's default `recursion_limit=25` fires (≈12 model+tool iterations),
# regardless of the user-set `max_iterations`. The ModelCallLimitMiddleware
# alone is insufficient because the graph-level recursion guard trips first.


@pytest.mark.asyncio
async def test_should_pass_recursion_limit_derived_from_max_iterations_when_streaming_events() -> None:
    """`run_agent` must pass a `recursion_limit` aligned with `max_iterations`.

    Without this, an Agent with `max_iterations=15` crashes at LangGraph's default
    25 graph steps (≈12 model+tool iterations) with `GraphRecursionError: Recursion
    limit of 25 reached` — long before the ModelCallLimitMiddleware's 15-call cap
    would have taken effect. The graph guard MUST sit above the middleware so the
    middleware's user-facing cap is what bounds the loop.

    Each iteration is roughly 2 graph steps (model node + tools node) plus a small
    constant overhead, so `recursion_limit >= max_iterations * 2 + 5` is the bare
    minimum that lets the middleware fire first.
    """
    captured_config: dict = {}

    def _capture_astream(_input_dict, *, config, **_kwargs):
        captured_config.update(config or {})
        return _empty_event_stream()

    fake_graph = MagicMock(spec=CompiledStateGraph)
    fake_graph.astream_events = _capture_astream

    component = _build_component()
    component.set_attributes({"max_iterations": 15, "input_value": "hi", "chat_history": []})

    final_message = MagicMock()
    final_message.get_id.return_value = None
    final_message.properties = MagicMock()

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch(
            "lfx.components.models_and_agents.agent.process_agent_events",
            new=AsyncMock(return_value=final_message),
        ),
    ):
        await component.run_agent(fake_graph)

    assert "recursion_limit" in captured_config, (
        "run_agent must pass `recursion_limit` to astream_events; otherwise LangGraph's "
        "default of 25 fires before ModelCallLimitMiddleware reaches the user-set cap "
        "(UI-009/UI-010 regression)."
    )
    # Each user-visible iteration is ~2 graph steps (model + tools), plus overhead.
    assert captured_config["recursion_limit"] >= 15 * 2 + 5, (
        f"recursion_limit must sit above max_iterations * 2 + safety; got "
        f"{captured_config['recursion_limit']} for max_iterations=15"
    )


@pytest.mark.asyncio
async def test_should_complete_run_agent_synchronously_before_returning_so_downstream_agents_see_final_state() -> None:
    """Regression guard for QA UI-012 (multi-agent chains).

    The QA report claimed "tools of downstream agents fire concurrently with
    Agent 1 still running", evidenced by chain spans aggregating to ~474s while
    wall time was ~207s. Investigation found:
      - `agent.py`'s `run_agent` `await`s `process_agent_events` fully before
        returning a Message; it does NOT spawn unawaited tasks.
      - `lfx/graph/graph/base.py` runs vertices in topological layers; each
        layer's `asyncio.gather(*tasks)` must resolve before the next layer
        starts. So downstream `Agent` vertices wired by `input_value` cannot
        start until upstream agents complete.
      - The 474s vs 207s discrepancy in the QA trace is consistent with
        nested-span accounting in LangGraph (parent spans wrap child spans,
        and aggregate sums double-count), NOT with concurrent agent execution.

    This test pins the agent-side contract: `message_response` only returns
    when run_agent has fully resolved. If a future refactor introduces a
    fire-and-forget pattern, this test catches it before the regression ships.
    """
    captured_calls: list[tuple[str, float]] = []

    fake_graph = MagicMock(spec=CompiledStateGraph)
    fake_graph.astream_events = lambda *_args, **_kwargs: _empty_event_stream()

    async def _record_then_return(_stream, agent_message, *_args, **_kwargs):
        from time import perf_counter

        captured_calls.append(("process_start", perf_counter()))
        captured_calls.append(("process_end", perf_counter()))
        return agent_message

    component = _build_component()
    component.set_attributes({"input_value": "hi", "chat_history": []})

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch(
            "lfx.components.models_and_agents.agent.process_agent_events",
            side_effect=_record_then_return,
        ),
    ):
        from time import perf_counter

        before = perf_counter()
        await component.run_agent(fake_graph)
        after = perf_counter()

    process_start_ts = next(ts for name, ts in captured_calls if name == "process_start")
    process_end_ts = next(ts for name, ts in captured_calls if name == "process_end")

    assert before <= process_start_ts <= process_end_ts <= after, (
        "run_agent must fully await process_agent_events before returning. A future change "
        "that fires this off as a background task would break multi-agent chain semantics."
    )


@pytest.mark.asyncio
async def test_should_pass_recursion_limit_when_max_iterations_is_clamped_from_zero() -> None:
    """`recursion_limit` must use the clamped `max_iterations`, not the raw user input.

    A saved `max_iterations=0` is clamped to >=1 by `_build_middleware`; the
    recursion_limit derived in `run_agent` must use that same clamped value, not
    the raw user input. Otherwise we'd pass `recursion_limit=5` (5 = safety only)
    and the agent couldn't run even one iteration.
    """
    captured_config: dict = {}

    def _capture_astream(_input_dict, *, config, **_kwargs):
        captured_config.update(config or {})
        return _empty_event_stream()

    fake_graph = MagicMock(spec=CompiledStateGraph)
    fake_graph.astream_events = _capture_astream

    component = _build_component()
    component.set_attributes({"max_iterations": 0, "input_value": "hi", "chat_history": []})

    final_message = MagicMock()
    final_message.get_id.return_value = None
    final_message.properties = MagicMock()

    with (
        patch.object(type(component), "_get_shared_callbacks", return_value=[]),
        patch(
            "lfx.components.models_and_agents.agent.process_agent_events",
            new=AsyncMock(return_value=final_message),
        ),
    ):
        await component.run_agent(fake_graph)

    # Clamped max_iterations=1 → at least 1*2+5 = 7 graph steps must be allowed.
    assert captured_config.get("recursion_limit", 0) >= 7, (
        "Clamped max_iterations of 1 must still permit at least one model+tool round-trip"
    )


@pytest.mark.asyncio
async def test_should_pass_stream_true_to_get_llm_when_self_stream_toggle_is_false() -> None:
    """Streaming is mandatory for AgentComponent.

    The LLM must always be instantiated with ``stream=True`` so ``astream_events(v2)``
    emits ``on_chat_model_stream`` chunks.

    Bug: when ``self.stream`` (the legacy BoolInput toggle introduced in PR #13155) is
    False, ``_get_llm`` forwards ``stream=False`` to ``get_llm`` and ChatOpenAI is built
    with ``streaming=False``. LangGraph then accumulates the response and only emits
    ``on_chat_model_end``, so the Playground/API surface stops receiving tokens
    incrementally — i.e. the live-typing UX is silently disabled.

    The Agent has no opt-out from streaming (see
    ``reference_agent_streaming_mandatory.md``); the toggle is a leftover and the
    underlying ``get_llm`` call must always use ``stream=True``.
    """
    captured: dict[str, Any] = {}

    def _capture_get_llm(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="fake_chat_model")

    component = _build_component()
    component.set_attributes({"stream": False})

    with patch("lfx.components.models_and_agents.agent.get_llm", side_effect=_capture_get_llm):
        component._get_llm()

    assert captured.get("stream") is True, (
        "AgentComponent._get_llm must hard-code stream=True regardless of the BoolInput "
        f"toggle value — got stream={captured.get('stream')!r}. Without it the underlying "
        "ChatOpenAI is built with streaming=False and astream_events stops emitting "
        "on_chat_model_stream chunks."
    )


@pytest.mark.asyncio
async def test_should_pass_stream_true_to_get_llm_when_self_stream_toggle_is_true() -> None:
    """Sanity check that an explicit stream=True toggle still reaches get_llm.

    When the user explicitly toggles stream=True, get_llm must still receive stream=True.
    This guards against a regression where the toggle inverts the flag or is consumed
    elsewhere before reaching get_llm.
    """
    captured: dict[str, Any] = {}

    def _capture_get_llm(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="fake_chat_model")

    component = _build_component()
    component.set_attributes({"stream": True})

    with patch("lfx.components.models_and_agents.agent.get_llm", side_effect=_capture_get_llm):
        component._get_llm()

    assert captured.get("stream") is True
