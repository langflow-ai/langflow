"""Agent integration of the "Summarize Older Messages" toggle."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage
from lfx.base.memory.session_compressor import build_summary_message
from lfx.components.models_and_agents import agent as agent_module
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.agent_helpers.messages_input_builder import build_initial_messages
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_USER


def _component(*, summarize: bool, n_messages: int = 10) -> AgentComponent:
    component = AgentComponent()
    component._user_id = None
    component.set_attributes(
        {
            "model": "fake-model",
            "tools": [],
            "chat_history": [],
            "input_value": Message(text="now", sender=MESSAGE_SENDER_USER, id=uuid.uuid4()),
            "summarize_older_messages": summarize,
            "n_messages": n_messages,
            "context_id": "",
        }
    )
    component._vertex = SimpleNamespace(graph=SimpleNamespace(session_id="s", flow_id=None, user_id=None))
    return component


def _history(component: AgentComponent) -> list[Message]:
    prior = Message(text="earlier", sender=MESSAGE_SENDER_USER, id=uuid.uuid4())
    return [prior, component.input_value]


async def test_toggle_off_returns_window_without_compressor():
    component = _component(summarize=False)
    history = _history(component)
    with (
        patch.object(agent_module, "aget_agent_chat_history", new=AsyncMock(return_value=history)),
        patch.object(agent_module, "build_history_with_summary", new=AsyncMock()) as compressor,
    ):
        result = await component.get_memory_data()
    assert result == history[:1]
    compressor.assert_not_called()


async def test_toggle_on_prepends_user_role_summary_message():
    component = _component(summarize=True)
    history = _history(component)
    summary = build_summary_message("KEY FACT", "s")
    compressed = [summary, history[0]]
    with (
        patch.object(agent_module, "aget_agent_chat_history", new=AsyncMock(return_value=history)),
        patch.object(agent_module, "build_history_with_summary", new=AsyncMock(return_value=compressed)) as compressor,
    ):
        result = await component.get_memory_data()
    assert compressor.call_args.kwargs["window"] == history[:1]
    assert result[0] is summary
    lc_messages = build_initial_messages(input_value=component.input_value, chat_history=result)
    assert isinstance(lc_messages[0], HumanMessage)
    assert "KEY FACT" in lc_messages[0].content


async def test_summary_is_computed_once_per_input():
    component = _component(summarize=True)
    history = _history(component)
    with (
        patch.object(agent_module, "aget_agent_chat_history", new=AsyncMock(return_value=history)),
        patch.object(agent_module, "build_history_with_summary", new=AsyncMock(return_value=history[:1])) as compressor,
    ):
        await component.get_memory_data()
        await component.get_memory_data()
    assert compressor.call_count == 1
