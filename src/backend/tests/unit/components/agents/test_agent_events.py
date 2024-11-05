from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

from langflow.base.agents.agent import process_agent_events


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
    assert "test input" in result.content_blocks[0].content.text


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
    assert result.content_blocks[0].content.tool_name == "test_tool"
    assert result.content_blocks[0].content.tool_input == {"query": "tool input"}  # Updated assertion


async def test_tool_end_event():
    """Test handling of on_tool_end event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [{"event": "on_tool_end", "name": "test_tool", "data": {"output": "tool output"}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Tool Output"
    assert result.content_blocks[0].content.tool_name == "test_tool"
    assert result.content_blocks[0].content.tool_output == "tool output"


async def test_tool_error_event():
    """Test handling of on_tool_error event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [{"event": "on_tool_error", "name": "test_tool", "data": {"error": "error message"}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.icon == "⚠️"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Tool Error"
    assert result.content_blocks[0].content.tool_name == "test_tool"
    assert result.content_blocks[0].content.tool_error == "error message"


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
