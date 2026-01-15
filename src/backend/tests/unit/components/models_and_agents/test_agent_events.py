from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessageChunk
from lfx.base.agents.events import (
    _extract_output_text,
    handle_on_chain_end,
    handle_on_chain_start,
    handle_on_chain_stream,
    handle_on_tool_end,
    handle_on_tool_error,
    handle_on_tool_start,
    process_agent_events,
)
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import ToolContent
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


async def create_event_iterator(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    """Helper function to create an async iterator from a list of events."""
    for event in events:
        yield event


def create_mock_send_message():
    """Create a mock send_message callback that simulates database ID assignment.

    In production, the first call to send_message persists to the database and assigns an ID.
    This mock simulates that behavior for testing.
    """
    call_count = [0]

    def mock_send_message(message, skip_db_update=False):  # noqa: ARG001, FBT002
        call_count[0] += 1
        if call_count[0] == 1:
            # Simulate production: add ID on first call (when persisting to DB)
            message.data["id"] = "test-message-id"
        return message

    return AsyncMock(side_effect=mock_send_message)


@pytest.mark.asyncio
async def test_chain_start_event():
    """Test handling of on_chain_start event."""
    send_message = create_mock_send_message()

    events = [
        {"event": "on_chain_start", "data": {"input": {"input": "test input", "chat_history": []}}, "start_time": 0}
    ]

    # Initialize message with content blocks
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )

    result = await process_agent_events(create_event_iterator(events), agent_message, send_message)

    assert result.properties.icon == "Bot"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Agent Steps"


@pytest.mark.asyncio
async def test_chain_end_event():
    """Test handling of on_chain_end event."""
    send_message = create_mock_send_message()

    # Create a mock AgentFinish output
    output = AgentFinish(return_values={"output": "final output"}, log="test log")

    events = [{"event": "on_chain_end", "data": {"output": output}, "start_time": 0}]

    # Initialize message with content blocks
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )

    result = await process_agent_events(create_event_iterator(events), agent_message, send_message)

    assert result.properties.icon == "Bot"
    assert result.properties.state == "complete"
    assert result.text == "final output"


@pytest.mark.asyncio
async def test_tool_start_event():
    """Test handling of on_tool_start event."""
    call_count = [0]

    def update_message(message, skip_db_update=False):  # noqa: ARG001, FBT002
        call_count[0] += 1
        if call_count[0] == 1:
            # Simulate production: add ID on first call (when persisting to DB)
            message.data["id"] = "test-message-id"
        # Return a copy of the message to simulate real behavior
        return Message(**message.model_dump())

    send_message = AsyncMock(side_effect=update_message)

    events = [
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"input": {"query": "tool input"}},
            "start_time": 0,
        }
    ]
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )
    result = await process_agent_events(create_event_iterator(events), agent_message, send_message)

    assert result.properties.icon == "Bot"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Agent Steps"
    assert len(result.content_blocks[0].contents) > 0
    tool_content = result.content_blocks[0].contents[-1]
    assert isinstance(tool_content, ToolContent)
    assert tool_content.name == "test_tool"
    assert tool_content.tool_input == {"query": "tool input"}, tool_content


@pytest.mark.asyncio
async def test_tool_end_event():
    """Test handling of on_tool_end event."""
    send_message = create_mock_send_message()

    events = [
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"input": {"query": "tool input"}},
            "start_time": 0,
        },
        {
            "event": "on_tool_end",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"output": "tool output"},
            "start_time": 0,
        },
    ]
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )
    result = await process_agent_events(create_event_iterator(events), agent_message, send_message)

    assert len(result.content_blocks) == 1
    tool_content = result.content_blocks[0].contents[-1]
    assert tool_content.name == "test_tool"
    assert tool_content.output == "tool output"


@pytest.mark.asyncio
async def test_tool_error_event():
    """Test handling of on_tool_error event."""
    send_message = create_mock_send_message()

    events = [
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"input": {"query": "tool input"}},
            "start_time": 0,
        },
        {
            "event": "on_tool_error",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"error": "error message"},
            "start_time": 0,
        },
    ]
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )

    result = await process_agent_events(create_event_iterator(events), agent_message, send_message)

    tool_content = result.content_blocks[0].contents[-1]
    assert tool_content.name == "test_tool"
    assert tool_content.error == "error message"
    assert tool_content.header["title"] == "Error using **test_tool**"


@pytest.mark.asyncio
async def test_chain_stream_event():
    """Test handling of on_chain_stream event."""
    send_message = create_mock_send_message()

    events = [{"event": "on_chain_stream", "data": {"chunk": {"output": "streamed output"}}, "start_time": 0}]
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )
    result = await process_agent_events(create_event_iterator(events), agent_message, send_message)

    assert result.properties.state == "complete"
    assert result.text == "streamed output"


@pytest.mark.asyncio
async def test_multiple_events():
    """Test handling of multiple events in sequence."""
    send_message = create_mock_send_message()

    # Create a mock AgentFinish output instead of MockOutput
    output = AgentFinish(return_values={"output": "final output"}, log="test log")

    events = [
        {"event": "on_chain_start", "data": {"input": {"input": "initial input", "chat_history": []}}, "start_time": 0},
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"input": {"query": "tool input"}},
            "start_time": 0,
        },
        {
            "event": "on_tool_end",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"output": "tool output"},
            "start_time": 0,
        },
        {"event": "on_chain_end", "data": {"output": output}, "start_time": 0},
    ]

    # Initialize message with content blocks
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    result = await process_agent_events(create_event_iterator(events), agent_message, send_message)

    assert result.properties.state == "complete"
    assert result.properties.icon == "Bot"
    assert len(result.content_blocks) == 1
    assert result.text == "final output"


@pytest.mark.asyncio
async def test_unknown_event():
    """Test handling of unknown event type."""
    send_message = create_mock_send_message()
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],  # Initialize with empty content block
    )

    events = [{"event": "unknown_event", "data": {"some": "data"}, "start_time": 0}]

    result = await process_agent_events(create_event_iterator(events), agent_message, send_message)

    # Should complete without error and maintain default state
    assert result.properties.state == "complete"
    # Content blocks should be empty but present
    assert len(result.content_blocks) == 1
    assert len(result.content_blocks[0].contents) == 0


# Additional tests for individual handler functions


@pytest.mark.asyncio
async def test_handle_on_chain_start_with_input():
    """Test handle_on_chain_start with input."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {"event": "on_chain_start", "data": {"input": {"input": "test input", "chat_history": []}}, "start_time": 0}

    updated_message, start_time = await handle_on_chain_start(event, agent_message, send_message, None, 0.0)

    assert updated_message.properties.icon == "Bot"
    assert len(updated_message.content_blocks) == 1
    assert updated_message.content_blocks[0].title == "Agent Steps"
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_chain_start_no_input():
    """Test handle_on_chain_start without input."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {"event": "on_chain_start", "data": {}, "start_time": 0}

    updated_message, start_time = await handle_on_chain_start(event, agent_message, send_message, None, 0.0)

    assert updated_message.properties.icon == "Bot"
    assert len(updated_message.content_blocks) == 1
    assert len(updated_message.content_blocks[0].contents) == 0
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_chain_end_with_output():
    """Test handle_on_chain_end with output."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    output = AgentFinish(return_values={"output": "final output"}, log="test log")
    event = {"event": "on_chain_end", "data": {"output": output}, "start_time": 0}

    updated_message, start_time = await handle_on_chain_end(event, agent_message, send_message, None, 0.0)

    assert updated_message.properties.icon == "Bot"
    assert updated_message.properties.state == "complete"
    assert updated_message.text == "final output"
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_chain_end_no_output():
    """Test handle_on_chain_end without output key in data."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {"event": "on_chain_end", "data": {}, "start_time": 0}

    updated_message, start_time = await handle_on_chain_end(event, agent_message, send_message, None, 0.0)

    assert updated_message.properties.icon == "Bot"
    assert updated_message.properties.state == "partial"
    assert updated_message.text == ""
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_chain_end_empty_data():
    """Test handle_on_chain_end with empty data."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {"event": "on_chain_end", "data": {"output": None}, "start_time": 0}

    updated_message, start_time = await handle_on_chain_end(event, agent_message, send_message, None, 0.0)

    assert updated_message.properties.icon == "Bot"
    assert updated_message.properties.state == "partial"
    assert updated_message.text == ""
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_chain_end_with_empty_return_values():
    """Test handle_on_chain_end with empty return_values."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    class MockOutputEmptyReturnValues:
        def __init__(self):
            self.return_values = {}

    event = {"event": "on_chain_end", "data": {"output": MockOutputEmptyReturnValues()}, "start_time": 0}

    updated_message, start_time = await handle_on_chain_end(event, agent_message, send_message, None, 0.0)

    assert updated_message.properties.icon == "Bot"
    assert updated_message.properties.state == "partial"
    assert updated_message.text == ""
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_tool_start():
    """Test handle_on_tool_start event."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    tool_blocks_map = {}
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {
        "event": "on_tool_start",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"input": {"query": "tool input"}},
        "start_time": 0,
    }

    updated_message, start_time = await handle_on_tool_start(event, agent_message, tool_blocks_map, send_message, 0.0)

    assert len(updated_message.content_blocks) == 1
    assert len(updated_message.content_blocks[0].contents) > 0
    tool_key = f"{event['name']}_{event['run_id']}"
    tool_content = updated_message.content_blocks[0].contents[-1]
    assert tool_content == tool_blocks_map.get(tool_key)
    assert isinstance(tool_content, ToolContent)
    assert tool_content.name == "test_tool"
    assert tool_content.tool_input == {"query": "tool input"}
    assert isinstance(tool_content.duration, int)
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_tool_end():
    """Test handle_on_tool_end event."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    tool_blocks_map = {}
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    start_event = {
        "event": "on_tool_start",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"input": {"query": "tool input"}},
    }
    agent_message, _ = await handle_on_tool_start(start_event, agent_message, tool_blocks_map, send_message, 0.0)

    end_event = {
        "event": "on_tool_end",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"output": "tool output"},
        "start_time": 0,
    }

    updated_message, start_time = await handle_on_tool_end(end_event, agent_message, tool_blocks_map, send_message, 0.0)

    f"{end_event['name']}_{end_event['run_id']}"
    tool_content = updated_message.content_blocks[0].contents[-1]
    assert tool_content.name == "test_tool"
    assert tool_content.output == "tool output"
    assert isinstance(tool_content.duration, int)
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_tool_error():
    """Test handle_on_tool_error event."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    tool_blocks_map = {}
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    start_event = {
        "event": "on_tool_start",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"input": {"query": "tool input"}},
    }
    agent_message, _ = await handle_on_tool_start(start_event, agent_message, tool_blocks_map, send_message, 0.0)

    error_event = {
        "event": "on_tool_error",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"error": "error message"},
        "start_time": 0,
    }

    updated_message, start_time = await handle_on_tool_error(
        error_event, agent_message, tool_blocks_map, send_message, 0.0
    )

    tool_content = updated_message.content_blocks[0].contents[-1]
    assert tool_content.name == "test_tool"
    assert tool_content.error == "error message"
    assert tool_content.header["title"] == "Error using **test_tool**"
    assert isinstance(tool_content.duration, int)
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_chain_stream_with_output():
    """Test handle_on_chain_stream with output."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {
        "event": "on_chain_stream",
        "data": {"chunk": {"output": "streamed output"}},
    }

    updated_message, start_time = await handle_on_chain_stream(event, agent_message, send_message, None, 0.0)

    assert updated_message.text == "streamed output"
    assert updated_message.properties.state == "complete"
    assert isinstance(start_time, float)


@pytest.mark.asyncio
async def test_handle_on_chain_stream_no_output():
    """Test handle_on_chain_stream without output."""
    send_message = AsyncMock(side_effect=lambda message, skip_db_update=False: message)  # noqa: ARG005
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )
    event = {
        "event": "on_chain_stream",
        "data": {"chunk": {}},
    }

    updated_message, start_time = await handle_on_chain_stream(event, agent_message, send_message, None, 0.0)

    assert updated_message.text == ""
    assert updated_message.properties.state == "partial"
    assert isinstance(start_time, float)


# Comprehensive tests for _extract_output_text function


def test_extract_output_text_string_input():
    """Test _extract_output_text with string input (backward compatibility)."""
    result = _extract_output_text("simple text output")
    assert result == "simple text output"


def test_extract_output_text_empty_string():
    """Test _extract_output_text with empty string."""
    result = _extract_output_text("")
    assert result == ""


def test_extract_output_text_empty_list():
    """Test _extract_output_text with empty list."""
    result = _extract_output_text([])
    assert result == ""


def test_extract_output_text_single_string_in_list():
    """Test _extract_output_text with single string in list."""
    result = _extract_output_text(["text content"])
    assert result == "text content"


def test_extract_output_text_single_dict_with_text():
    """Test _extract_output_text with single dict containing 'text' key (backward compatibility)."""
    result = _extract_output_text([{"text": "message content"}])
    assert result == "message content"


def test_extract_output_text_tool_use_type():
    """Test _extract_output_text with tool_use type (backward compatibility)."""
    result = _extract_output_text([{"type": "tool_use", "name": "some_tool"}])
    assert result == ""


def test_extract_output_text_partial_json():
    """Test _extract_output_text with partial_json (backward compatibility)."""
    result = _extract_output_text([{"partial_json": '{"incomplete": true'}])
    assert result == ""


def test_extract_output_text_chatbedrockconverse_index_only():
    """Test _extract_output_text with ChatBedrockConverse index-only format (NEW FIX)."""
    # This is the specific case that was failing before the fix
    result = _extract_output_text([{"index": 0}])
    assert result == ""


def test_extract_output_text_chatbedrockconverse_index_with_extra_data():
    """Test _extract_output_text with ChatBedrockConverse index plus other data."""
    result = _extract_output_text([{"index": 0, "some_other_field": "value"}])
    assert result == ""


def test_extract_output_text_multiple_items_mixed():
    """Test _extract_output_text with multiple items including text and non-text."""
    result = _extract_output_text(
        [{"text": "First part"}, {"type": "tool_use", "name": "some_tool"}, {"text": "Second part"}, {"index": 0}]
    )
    assert result == "First partSecond part"


def test_extract_output_text_multiple_strings():
    """Test _extract_output_text with multiple strings in list."""
    result = _extract_output_text(["Hello", " ", "World"])
    assert result == "Hello World"


def test_extract_output_text_mixed_strings_and_dicts():
    """Test _extract_output_text with mixed strings and text dicts."""
    result = _extract_output_text(["Start: ", {"text": "middle content"}, " End."])
    assert result == "Start: middle content End."


def test_extract_output_text_complex_chatbedrockconverse_response():
    """Test _extract_output_text with complex ChatBedrockConverse-like response."""
    result = _extract_output_text(
        [
            {"type": "text", "text": "I'll help you with that.", "index": 0},
            {"type": "tool_use", "name": "get_weather", "id": "tool_123", "index": 1},
            {"index": 2},  # Index-only item
        ]
    )
    assert result == "I'll help you with that."


def test_extract_output_text_all_non_text_items():
    """Test _extract_output_text with all non-text items."""
    result = _extract_output_text(
        [{"type": "tool_use", "name": "some_tool"}, {"index": 0}, {"partial_json": '{"incomplete": true'}]
    )
    assert result == ""


def test_extract_output_text_anthropic_style():
    """Test _extract_output_text with Anthropic-style response format."""
    result = _extract_output_text(
        [
            {"type": "text", "text": "Here's my response"},
            {"type": "tool_use", "name": "calculator", "input": {"expression": "2+2"}},
        ]
    )
    assert result == "Here's my response"


def test_extract_output_text_edge_case_none_values():
    """Test _extract_output_text with None/null values in dicts."""
    result = _extract_output_text([{"text": None}, {"text": "valid text"}, {"index": None}])
    assert result == "valid text"


def test_extract_output_text_edge_case_empty_text():
    """Test _extract_output_text with empty text values."""
    result = _extract_output_text([{"text": ""}, {"text": "actual content"}, {"text": ""}])
    assert result == "actual content"


def test_extract_output_text_single_dict_no_text_key():
    """Test _extract_output_text with dict that has no text key (graceful handling)."""
    result = _extract_output_text([{"some_field": "some_value"}])
    assert result == ""


def test_extract_output_text_single_dict_multiple_keys_no_text():
    """Test _extract_output_text with dict having multiple keys but no text."""
    result = _extract_output_text([{"field1": "value1", "field2": "value2"}])
    assert result == ""


def test_extract_output_text_realistic_streaming_scenario():
    """Test _extract_output_text with realistic streaming scenario."""
    # Simulate a streaming response with multiple chunks
    inputs = [
        [{"text": "I'm"}],
        [{"text": " thinking"}],
        [{"text": " about"}],
        [{"index": 0}],  # Empty streaming marker
        [{"text": " your"}],
        [{"text": " question."}],
    ]

    results = [_extract_output_text(inp) for inp in inputs]
    full_text = "".join(results)
    assert full_text == "I'm thinking about your question."


def test_extract_output_text_backward_compatibility_scenarios():
    """Test various backward compatibility scenarios that should still work."""
    # Original OpenAI/Anthropic style
    assert _extract_output_text([{"text": "response"}]) == "response"

    # Tool use should return empty
    assert _extract_output_text([{"type": "tool_use"}]) == ""

    # Partial JSON should return empty
    assert _extract_output_text([{"partial_json": "{}"}]) == ""

    # String input should work
    assert _extract_output_text("direct string") == "direct string"

    # Empty list should work
    assert _extract_output_text([]) == ""


def test_extract_output_text_chatbedrockconverse_compatibility():
    """Test all ChatBedrockConverse-specific scenarios that were causing errors."""
    # The specific failing case from the error message
    assert _extract_output_text([{"index": 0}]) == ""

    # Other index variations
    assert _extract_output_text([{"index": 1}]) == ""
    assert _extract_output_text([{"index": 10}]) == ""

    # Index with additional fields
    assert _extract_output_text([{"index": 0, "metadata": "something"}]) == ""

    # Multiple index-only items
    assert _extract_output_text([{"index": 0}, {"index": 1}]) == ""

    # Mixed with text
    assert _extract_output_text([{"text": "Hello"}, {"index": 0}]) == "Hello"


@pytest.mark.asyncio
async def test_agent_streaming_no_text_accumulation():
    """Test that agent streaming sends individual token events without accumulating text."""
    sent_messages = []
    token_events = []

    async def mock_send_message(message):
        # Capture each message sent for verification
        sent_messages.append(
            {"text": message.text, "state": message.properties.state, "id": getattr(message, "id", None)}
        )
        return message

    # Mock token callback to capture token events
    def mock_token_callback(data):
        # Capture token events
        token_events.append(data)

    event_manager = mock_token_callback

    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )
    # Add an ID to the message (normally set when persisted to DB)
    agent_message.data["id"] = "test-message-id"

    # Simulate streaming events with individual chunks
    events = [
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content="Hello")},
        },
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content=" world")},
        },
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content="!")},
        },
        {
            "event": "on_chain_end",
            "data": {"output": AgentFinish(return_values={"output": "Hello world!"}, log="complete")},
        },
    ]

    result = await process_agent_events(create_event_iterator(events), agent_message, mock_send_message, event_manager)

    # Verify individual token events were sent (not accumulated)
    assert len(token_events) == 3, f"Expected 3 token events, got {len(token_events)}"

    # Each token event should contain only its chunk, not accumulated text
    assert token_events[0]["chunk"] == "Hello"
    assert token_events[1]["chunk"] == " world"
    assert token_events[2]["chunk"] == "!"

    # Verify all token events have the correct message ID
    for token_event in token_events:
        assert "id" in token_event
        assert token_event["id"] == "test-message-id"

    # Verify no token event contains accumulated text
    for token_event in token_events:
        assert "Hello world!" not in token_event["chunk"], f"Found accumulated text in chunk: {token_event['chunk']}"

    # Final result should have complete message with full text
    assert result.properties.state == "complete"
    assert result.text == "Hello world!"


@pytest.mark.asyncio
async def test_agent_streaming_without_event_manager():
    """Test that agent streaming works without event_manager (backward compatibility)."""
    sent_messages = []
    call_count = [0]

    async def mock_send_message(message):
        call_count[0] += 1
        if call_count[0] == 1:
            # Simulate production: add ID on first call (when persisting to DB)
            message.data["id"] = "test-message-id"
        sent_messages.append(
            {"text": message.text, "state": message.properties.state, "id": getattr(message, "id", None)}
        )
        return message

    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )

    # Simulate streaming events with individual chunks but NO event_manager
    events = [
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content="Hello")},
        },
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content=" world")},
        },
        {
            "event": "on_chain_end",
            "data": {"output": AgentFinish(return_values={"output": "Hello world!"}, log="complete")},
        },
    ]

    # Call without event_manager parameter
    result = await process_agent_events(create_event_iterator(events), agent_message, mock_send_message)

    # Without event_manager, streaming chunks should not trigger send_message
    # Only initial message and final message should be sent
    assert result.properties.state == "complete"
    assert result.text == "Hello world!"


@pytest.mark.asyncio
async def test_agent_streaming_skips_empty_chunks():
    """Test that empty or whitespace-only chunks are skipped during streaming."""
    token_events = []

    async def mock_send_message(message):
        return message

    def mock_token_callback(data):
        token_events.append(data)

    event_manager = mock_token_callback

    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )
    # Add an ID to the message (normally set when persisted to DB)
    agent_message.data["id"] = "test-message-id-2"

    # Simulate streaming with empty/whitespace chunks mixed in
    events = [
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content="Hello")},
        },
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content="")},  # Empty - should be skipped
        },
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content="   ")},  # Whitespace - should be skipped
        },
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content=" world")},
        },
        {
            "event": "on_chain_end",
            "data": {"output": AgentFinish(return_values={"output": "Hello world"}, log="complete")},
        },
    ]

    result = await process_agent_events(create_event_iterator(events), agent_message, mock_send_message, event_manager)

    # Only non-empty chunks should generate token events
    assert len(token_events) == 2, f"Expected 2 token events (empty chunks skipped), got {len(token_events)}"
    assert token_events[0]["chunk"] == "Hello"
    assert token_events[1]["chunk"] == " world"
    assert result.properties.state == "complete"


@pytest.mark.asyncio
async def test_agent_streaming_preserves_message_id():
    """Test that agent streaming preserves message ID throughout event processing."""
    token_events = []
    call_count = [0]

    async def mock_send_message(message):
        # Simulate persisting the message and returning with ID on first call
        call_count[0] += 1
        if call_count[0] == 1:
            # First call - add the ID
            message.data["id"] = "test-persisted-id"
        return message

    def mock_token_callback(data):
        token_events.append(data)

    event_manager = mock_token_callback

    # Create message WITHOUT an ID initially
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        session_id="test_session_id",
    )

    events = [
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content="Hello")},
        },
        {
            "event": "on_chain_stream",
            "data": {"chunk": AIMessageChunk(content=" world")},
        },
        {
            "event": "on_chain_end",
            "data": {"output": AgentFinish(return_values={"output": "Hello world"}, log="complete")},
        },
    ]

    result = await process_agent_events(create_event_iterator(events), agent_message, mock_send_message, event_manager)

    # Verify token events were sent with the persisted ID
    assert len(token_events) == 2, f"Expected 2 token events, got {len(token_events)}"
    assert token_events[0]["chunk"] == "Hello"
    assert token_events[0]["id"] == "test-persisted-id"
    assert token_events[1]["chunk"] == " world"
    assert token_events[1]["id"] == "test-persisted-id"
    assert result.properties.state == "complete"
    assert result.text == "Hello world"
