"""Tests for handle_on_chain_start / handle_on_chain_end accepting the create_agent shape.

Slices S5–S6 of langchain_classic.AgentExecutor → langchain.agents.create_agent migration.

Under create_agent (CompiledStateGraph), `astream_events(version='v2')` emits:
  - on_chain_start.data.input  = {"messages": [HumanMessage, ...]}
  - on_chain_end.data.output  = {"messages": [HumanMessage, ..., AIMessage]}

The legacy AgentExecutor shape (`{"input": str, "chat_history": [...]}` /
`AgentFinish`) must remain supported during the transition window so any
remaining callers do not regress.
"""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessage, HumanMessage
from lfx.base.agents.events import process_agent_events
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import TextContent
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


async def _events_iter(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for event in events:
        yield event


def _send_message_mock() -> AsyncMock:
    call_count = [0]

    def _impl(message, skip_db_update=False):  # noqa: ARG001, FBT002
        call_count[0] += 1
        if call_count[0] == 1:
            message.data["id"] = "test-id"
        return message

    return AsyncMock(side_effect=_impl)


def _partial_message() -> Message:
    return Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test-session",
    )


@pytest.mark.asyncio
async def test_should_render_input_text_block_when_chain_start_emits_messages_input() -> None:
    events = [
        {
            "event": "on_chain_start",
            "data": {"input": {"messages": [HumanMessage(content="test input")]}},
            "start_time": 0,
        },
    ]

    result = await process_agent_events(_events_iter(events), _partial_message(), _send_message_mock())

    text_blocks = [c for c in result.content_blocks[0].contents if isinstance(c, TextContent)]
    assert any(c.text == "test input" for c in text_blocks)


@pytest.mark.asyncio
async def test_should_render_input_text_block_when_chain_start_messages_list_has_history() -> None:
    """If history is included, only the last HumanMessage drives the rendered Input block."""
    events = [
        {
            "event": "on_chain_start",
            "data": {
                "input": {
                    "messages": [
                        HumanMessage(content="prev user"),
                        AIMessage(content="prev ai"),
                        HumanMessage(content="latest input"),
                    ]
                }
            },
            "start_time": 0,
        },
    ]

    result = await process_agent_events(_events_iter(events), _partial_message(), _send_message_mock())

    text_blocks = [c for c in result.content_blocks[0].contents if isinstance(c, TextContent)]
    assert any(c.text == "latest input" for c in text_blocks)


@pytest.mark.asyncio
async def test_should_set_final_text_when_chain_end_emits_messages_state() -> None:
    final_state = {
        "messages": [
            HumanMessage(content="hi"),
            AIMessage(content="42"),
        ]
    }
    events = [{"event": "on_chain_end", "data": {"output": final_state}, "start_time": 0}]

    result = await process_agent_events(_events_iter(events), _partial_message(), _send_message_mock())

    assert result.text == "42"
    assert result.properties.state == "complete"


@pytest.mark.asyncio
async def test_should_set_final_text_from_list_content_when_chain_end_state_has_list_content() -> None:
    final_state = {
        "messages": [
            AIMessage(content=[{"type": "text", "text": "list answer"}]),
        ]
    }
    events = [{"event": "on_chain_end", "data": {"output": final_state}, "start_time": 0}]

    result = await process_agent_events(_events_iter(events), _partial_message(), _send_message_mock())

    assert result.text == "list answer"


@pytest.mark.asyncio
async def test_should_keep_supporting_legacy_agent_finish_when_chain_end_emits_agent_finish() -> None:
    """Backward compatibility: legacy AgentExecutor path must keep working."""
    events = [
        {
            "event": "on_chain_end",
            "data": {"output": AgentFinish(return_values={"output": "legacy answer"}, log="")},
            "start_time": 0,
        }
    ]

    result = await process_agent_events(_events_iter(events), _partial_message(), _send_message_mock())

    assert result.text == "legacy answer"


@pytest.mark.asyncio
async def test_should_keep_supporting_legacy_chain_start_when_input_dict_has_input_key() -> None:
    """Backward compatibility: legacy AgentExecutor `{"input": str, "chat_history": []}` shape."""
    events = [
        {
            "event": "on_chain_start",
            "data": {"input": {"input": "legacy input", "chat_history": []}},
            "start_time": 0,
        }
    ]

    result = await process_agent_events(_events_iter(events), _partial_message(), _send_message_mock())

    text_blocks = [c for c in result.content_blocks[0].contents if isinstance(c, TextContent)]
    assert any(c.text == "legacy input" for c in text_blocks)


@pytest.mark.asyncio
async def test_should_not_render_input_block_when_chain_start_messages_has_no_human_message() -> None:
    """If somehow only system/AI messages arrive, do not render an empty Input block."""
    events = [
        {
            "event": "on_chain_start",
            "data": {"input": {"messages": [AIMessage(content="not from user")]}},
            "start_time": 0,
        },
    ]

    result = await process_agent_events(_events_iter(events), _partial_message(), _send_message_mock())

    text_blocks = [c for c in result.content_blocks[0].contents if isinstance(c, TextContent)]
    assert not any(c.text == "not from user" for c in text_blocks)
