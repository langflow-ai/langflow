from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

from langflow.base.agents.agent import process_agent_events
from langflow.base.agents.events import (
    handle_on_chain_end,
    handle_on_chain_start,
    handle_on_chain_stream,
    handle_on_tool_end,
    handle_on_tool_error,
    handle_on_tool_start,
)
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI


async def create_event_iterator(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    """Helper function to create an async iterator from a list of events."""
    for event in events:
        yield event


async def test_chain_start_event():
    """Test handling of on_chain_start event."""
    # Mock the send_message function
    send_message = MagicMock(side_effect=lambda message: message)

    events = [{"event": "on_chain_start", "data": {"input": "test input"}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.icon == "🚀"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Agent Input"
    assert "test input" in result.content_blocks[0].contents.text


async def test_chain_end_event():
    """Test handling of on_chain_end event."""
    send_message = MagicMock(side_effect=lambda message: message)

    # Create a mock output object with return_values attribute
    class MockOutput:
        def __init__(self):
            self.return_values = {"output": "final output"}

    events = [{"event": "on_chain_end", "data": {"output": MockOutput()}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.icon == "🤖"
    assert result.properties.state == "complete"
    assert result.text == "final output"


async def test_tool_start_event():
    """Test handling of on_tool_start event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "data": {
                "input": {"query": "tool input"}  # Changed to dictionary
            },
        }
    ]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.icon == "🔧"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Tool Input"
    assert result.content_blocks[0].contents.tool_name == "test_tool"
    assert result.content_blocks[0].contents.tool_input == {"query": "tool input"}  # Updated assertion


async def test_tool_end_event():
    """Test handling of on_tool_end event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [{"event": "on_tool_end", "name": "test_tool", "data": {"output": "tool output"}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Tool Output"
    assert result.content_blocks[0].contents.tool_name == "test_tool"
    assert result.content_blocks[0].contents.tool_output == "tool output"


async def test_tool_error_event():
    """Test handling of on_tool_error event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [{"event": "on_tool_error", "name": "test_tool", "data": {"error": "error message"}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.icon == "⚠️"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Tool Error"
    assert result.content_blocks[0].contents.tool_name == "test_tool"
    assert result.content_blocks[0].contents.tool_error == "error message"


async def test_chain_stream_event():
    """Test handling of on_chain_stream event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [{"event": "on_chain_stream", "data": {"chunk": {"output": "streamed output"}}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.state == "complete"
    assert result.text == "streamed output"


async def test_multiple_events():
    """Test handling of multiple events in sequence."""
    send_message = MagicMock(side_effect=lambda message: message)

    # Create a mock output object with return_values attribute
    class MockOutput:
        def __init__(self):
            self.return_values = {"output": "final output"}

    events = [
        {"event": "on_chain_start", "data": {"input": "initial input"}},
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "data": {"input": {"query": "tool input"}},  # Changed to dictionary
        },
        {"event": "on_tool_end", "name": "test_tool", "data": {"output": "tool output"}},
        {"event": "on_chain_end", "data": {"output": MockOutput()}},  # Using MockOutput
    ]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.state == "complete"
    assert result.properties.icon == "🤖"
    assert len(result.content_blocks) == 3  # Start, Tool Start, Tool End
    assert result.text == "final output"


async def test_unknown_event():
    """Test handling of unknown event type."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [{"event": "unknown_event", "data": {"some": "data"}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    # Should complete without error and maintain default state
    assert result.properties.state == "complete"
    assert len(result.content_blocks) == 0


# Additional tests for individual handler functions


async def test_handle_on_chain_start_with_input():
    """Test handle_on_chain_start with input."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {"event": "on_chain_start", "data": {"input": "test input"}}

    updated_message = await handle_on_chain_start(event, agent_message, send_message)

    assert updated_message.properties.icon == "🚀"
    assert len(updated_message.content_blocks) == 1
    assert updated_message.content_blocks[0].title == "Agent Input"
    assert "test input" in updated_message.content_blocks[0].contents.text


async def test_handle_on_chain_start_no_input():
    """Test handle_on_chain_start without input."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {"event": "on_chain_start", "data": {}}

    updated_message = await handle_on_chain_start(event, agent_message, send_message)

    assert updated_message.properties.icon == "🤖"
    assert len(updated_message.content_blocks) == 0


async def test_handle_on_chain_end_with_output():
    """Test handle_on_chain_end with output."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )

    class MockOutput:
        def __init__(self):
            self.return_values = {"output": "final output"}

    event = {"event": "on_chain_end", "data": {"output": MockOutput()}}

    updated_message = await handle_on_chain_end(event, agent_message, send_message)

    assert updated_message.properties.icon == "🤖"
    assert updated_message.properties.state == "complete"
    assert updated_message.text == "final output"
    assert send_message.called


async def test_handle_on_chain_end_no_output():
    """Test handle_on_chain_end without output key in data."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {"event": "on_chain_end", "data": {}}  # No output key in data

    updated_message = await handle_on_chain_end(event, agent_message, send_message)

    assert updated_message.properties.icon == "🤖"  # Icon remains unchanged
    assert updated_message.properties.state == "partial"  # State remains unchanged
    assert updated_message.text == ""  # Text remains unchanged
    assert not send_message.called  # send_message should not be called


async def test_handle_on_chain_end_empty_data():
    """Test handle_on_chain_end with empty data."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {"event": "on_chain_end", "data": {"output": None}}

    updated_message = await handle_on_chain_end(event, agent_message, send_message)

    assert updated_message.properties.icon == "🤖"  # Icon remains unchanged
    assert updated_message.properties.state == "partial"  # State remains unchanged
    assert updated_message.text == ""  # Text remains unchanged
    assert not send_message.called  # send_message should not be called


async def test_handle_on_chain_end_with_empty_return_values():
    """Test handle_on_chain_end with empty return_values."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )

    class MockOutputEmptyReturnValues:
        def __init__(self):
            self.return_values = {}

    event = {"event": "on_chain_end", "data": {"output": MockOutputEmptyReturnValues()}}

    updated_message = await handle_on_chain_end(event, agent_message, send_message)

    assert updated_message.properties.icon == "🔍"
    assert updated_message.properties.state == "partial"  # State remains unchanged
    assert updated_message.text == ""  # Text remains unchanged
    assert send_message.called


async def test_handle_on_tool_start():
    """Test handle_on_tool_start event."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {
        "event": "on_tool_start",
        "name": "test_tool",
        "data": {"input": {"query": "tool input"}},
    }

    updated_message = await handle_on_tool_start(event, agent_message, send_message)

    assert updated_message.properties.icon == "🔧"
    assert len(updated_message.content_blocks) == 1
    assert updated_message.content_blocks[0].title == "Tool Input"
    assert updated_message.content_blocks[0].content.tool_name == "test_tool"
    assert updated_message.content_blocks[0].content.tool_input == {"query": "tool input"}


async def test_handle_on_tool_end():
    """Test handle_on_tool_end event."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {
        "event": "on_tool_end",
        "name": "test_tool",
        "data": {"output": "tool output"},
    }

    updated_message = await handle_on_tool_end(event, agent_message, send_message)

    assert len(updated_message.content_blocks) == 1
    assert updated_message.content_blocks[0].title == "Tool Output"
    assert updated_message.content_blocks[0].content.tool_name == "test_tool"
    assert updated_message.content_blocks[0].content.tool_output == "tool output"


async def test_handle_on_tool_error():
    """Test handle_on_tool_error event."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {
        "event": "on_tool_error",
        "name": "test_tool",
        "data": {"error": "error message"},
    }

    updated_message = await handle_on_tool_error(event, agent_message, send_message)

    assert updated_message.properties.icon == "⚠️"
    assert len(updated_message.content_blocks) == 1
    assert updated_message.content_blocks[0].title == "Tool Error"
    assert updated_message.content_blocks[0].content.tool_name == "test_tool"
    assert updated_message.content_blocks[0].content.tool_error == "error message"


async def test_handle_on_chain_stream_with_output():
    """Test handle_on_chain_stream with output."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {
        "event": "on_chain_stream",
        "data": {"chunk": {"output": "streamed output"}},
    }

    updated_message = await handle_on_chain_stream(event, agent_message, send_message)

    assert updated_message.text == "streamed output"
    assert updated_message.properties.state == "complete"


async def test_handle_on_chain_stream_no_output():
    """Test handle_on_chain_stream without output."""
    send_message = MagicMock(side_effect=lambda message: message)
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    event = {
        "event": "on_chain_stream",
        "data": {"chunk": {}},
    }

    updated_message = await handle_on_chain_stream(event, agent_message, send_message)

    assert updated_message.text == ""
    assert updated_message.properties.state == "partial"
