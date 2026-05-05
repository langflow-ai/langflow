"""Tests for LCAgentComponent.run_agent under the create_agent migration.

Slice S8 of langchain_classic.AgentExecutor → langchain.agents.create_agent migration.

run_agent must:
- Accept a `CompiledStateGraph` (the type returned by `create_agent`).
- Feed it the `{"messages": [BaseMessage, ...]}` input shape — NOT the legacy
  `{"input": str, "chat_history": [...]}` shape.
- Forward chat_history items via `messages` (not as a separate key).
- Preserve multimodal content as list-content `HumanMessage`s.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from lfx.base.agents.agent import LCAgentComponent
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


async def _empty_astream():
    return
    yield  # pragma: no cover — needed to make this an async generator


def _make_runnable_with_capture():
    """Return (runnable, captured) — runnable.astream_events writes its arg into captured."""
    captured: dict = {}

    def _capture(input_, **kwargs):
        captured["input"] = input_
        captured["kwargs"] = kwargs
        return _empty_astream()

    runnable = MagicMock(spec=Runnable)
    runnable.astream_events.side_effect = _capture
    return runnable, captured


def _make_component(input_value=None, chat_history=None) -> LCAgentComponent:
    class _Concrete(LCAgentComponent):
        def create_agent_runnable(self) -> Runnable:
            return MagicMock()

    component = _Concrete.__new__(_Concrete)
    component._token_usage = None
    component._vertex = SimpleNamespace(graph=SimpleNamespace(session_id=None, flow_id=None, user_id=None))
    component._event_manager = None
    component.tools = []
    component.input_value = input_value
    component.chat_history = chat_history or []
    component.status = None
    component.send_message = AsyncMock(return_value=Message(text="dummy"))
    component._get_shared_callbacks = MagicMock(return_value=[])
    component.log = MagicMock()
    return component


@pytest.mark.asyncio
async def test_should_call_astream_events_with_messages_shape_when_input_is_string() -> None:
    runnable, captured = _make_runnable_with_capture()
    result_message = Message(text="response", id="msg-id")

    with patch(
        "lfx.base.agents.agent.process_agent_events",
        new_callable=AsyncMock,
        return_value=result_message,
    ):
        component = _make_component(input_value="hello agent")
        await component.run_agent(runnable)

    assert captured["input"] == {"messages": [HumanMessage(content="hello agent")]} or _input_messages_match(
        captured["input"], expected=["hello agent"]
    )


@pytest.mark.asyncio
async def test_should_call_astream_events_with_messages_shape_when_input_is_message() -> None:
    runnable, captured = _make_runnable_with_capture()
    result_message = Message(text="response", id="msg-id")

    with patch(
        "lfx.base.agents.agent.process_agent_events",
        new_callable=AsyncMock,
        return_value=result_message,
    ):
        msg = Message(text="hi from message", sender=MESSAGE_SENDER_USER)
        component = _make_component(input_value=msg)
        await component.run_agent(runnable)

    assert "messages" in captured["input"]
    assert "input" not in captured["input"]
    assert "chat_history" not in captured["input"]


@pytest.mark.asyncio
async def test_should_include_chat_history_in_messages_list_when_history_provided() -> None:
    runnable, captured = _make_runnable_with_capture()
    result_message = Message(text="response", id="msg-id")

    with patch(
        "lfx.base.agents.agent.process_agent_events",
        new_callable=AsyncMock,
        return_value=result_message,
    ):
        history = [
            Data(text="prev user", sender=MESSAGE_SENDER_USER),
            Data(text="prev ai", sender=MESSAGE_SENDER_AI),
        ]
        component = _make_component(input_value="follow up", chat_history=history)
        await component.run_agent(runnable)

    msgs = captured["input"]["messages"]
    assert len(msgs) == 3
    # chat history first, current input last
    assert _content_text(msgs[-1]) == "follow up"


@pytest.mark.asyncio
async def test_should_default_to_continue_message_when_input_is_empty() -> None:
    runnable, captured = _make_runnable_with_capture()
    result_message = Message(text="response", id="msg-id")

    with patch(
        "lfx.base.agents.agent.process_agent_events",
        new_callable=AsyncMock,
        return_value=result_message,
    ):
        component = _make_component(input_value="")
        await component.run_agent(runnable)

    msgs = captured["input"]["messages"]
    assert any(_content_text(m) == "Continue the conversation." for m in msgs)


@pytest.mark.asyncio
async def test_should_pass_callbacks_via_config_kwarg_when_running_runnable() -> None:
    runnable, captured = _make_runnable_with_capture()
    result_message = Message(text="response", id="msg-id")

    with patch(
        "lfx.base.agents.agent.process_agent_events",
        new_callable=AsyncMock,
        return_value=result_message,
    ):
        component = _make_component(input_value="hello")
        await component.run_agent(runnable)

    config = captured["kwargs"].get("config", {})
    callbacks = config.get("callbacks", [])
    # AgentAsyncHandler + TokenUsageCallbackHandler at minimum
    assert len(callbacks) >= 2


@pytest.mark.asyncio
async def test_should_pass_version_v2_when_calling_astream_events() -> None:
    runnable, captured = _make_runnable_with_capture()
    result_message = Message(text="response", id="msg-id")

    with patch(
        "lfx.base.agents.agent.process_agent_events",
        new_callable=AsyncMock,
        return_value=result_message,
    ):
        component = _make_component(input_value="hello")
        await component.run_agent(runnable)

    assert captured["kwargs"].get("version") == "v2"


def _content_text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return "".join(parts)
    return ""


def _input_messages_match(input_dict, *, expected: list[str]) -> bool:
    msgs = input_dict.get("messages") if isinstance(input_dict, dict) else None
    if msgs is None or len(msgs) != len(expected):
        return False
    return all(_content_text(m) == e for m, e in zip(msgs, expected, strict=True))
