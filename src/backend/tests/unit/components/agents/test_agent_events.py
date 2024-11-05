from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

from langchain_core.agents import AgentFinish
from langflow.base.agents.agent import process_agent_events
from langflow.base.agents.events import (
    handle_on_chain_end,
    handle_on_chain_start,
    handle_on_chain_stream,
    handle_on_tool_end,
    handle_on_tool_error,
    handle_on_tool_start,
)
from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import ToolContent
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI


async def create_event_iterator(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    """Helper function to create an async iterator from a list of events."""
    for event in events:
        yield event


async def test_chain_start_event():
    """Test handling of on_chain_start event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [{"event": "on_chain_start", "data": {"input": {"input": "test input", "chat_history": []}}}]

    # Initialize message with content blocks
    initial_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    send_message.return_value = initial_message

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.icon == "Bot"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Agent Steps"


async def test_chain_end_event():
    """Test handling of on_chain_end event."""
    send_message = MagicMock(side_effect=lambda message: message)

    # Create a mock AgentFinish output
    output = AgentFinish(return_values={"output": "final output"}, log="test log")

    events = [{"event": "on_chain_end", "data": {"output": output}}]

    # Initialize message with content blocks
    initial_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    send_message.return_value = initial_message

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.icon == "Bot"
    assert result.properties.state == "complete"
    assert result.text == "final output"


async def test_tool_start_event():
    """Test handling of on_tool_start event."""
    send_message = MagicMock()

    # Set up the send_message mock to return the modified message
    def update_message(message):
        # Return a copy of the message to simulate real behavior
        return Message(**message.model_dump())

    send_message.side_effect = update_message

    events = [
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"input": {"query": "tool input"}},
        }
    ]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.icon == "Bot"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].title == "Agent Steps"
    assert len(result.content_blocks[0].contents) > 0
    tool_content = result.content_blocks[0].contents[-1]
    assert isinstance(tool_content, ToolContent)
    assert tool_content.name == "test_tool"
    assert tool_content.tool_input == {"query": "tool input"}, tool_content


async def test_tool_end_event():
    """Test handling of on_tool_end event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"input": {"query": "tool input"}},
        },
        {"event": "on_tool_end", "name": "test_tool", "run_id": "test_run", "data": {"output": "tool output"}},
    ]

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert len(result.content_blocks) == 1
    tool_content = result.content_blocks[0].contents[-1]
    assert tool_content.name == "test_tool"
    assert tool_content.output == "tool output"


async def test_tool_error_event():
    """Test handling of on_tool_error event."""
    send_message = MagicMock(side_effect=lambda message: message)

    events = [
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"input": {"query": "tool input"}},
        },
        {"event": "on_tool_error", "name": "test_tool", "run_id": "test_run", "data": {"error": "error message"}},
    ]

    result = await process_agent_events(create_event_iterator(events), send_message)

    tool_content = result.content_blocks[0].contents[-1]
    assert tool_content.name == "test_tool"
    assert tool_content.error == "error message"
    assert tool_content.header["title"] == "Error using **test_tool**"


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

    # Create a mock AgentFinish output instead of MockOutput
    output = AgentFinish(return_values={"output": "final output"}, log="test log")

    events = [
        {"event": "on_chain_start", "data": {"input": {"input": "initial input", "chat_history": []}}},
        {
            "event": "on_tool_start",
            "name": "test_tool",
            "run_id": "test_run",
            "data": {"input": {"query": "tool input"}},
        },
        {"event": "on_tool_end", "name": "test_tool", "run_id": "test_run", "data": {"output": "tool output"}},
        {"event": "on_chain_end", "data": {"output": output}},  # Use AgentFinish instead
    ]

    # Initialize message with content blocks
    initial_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    send_message.return_value = initial_message

    result = await process_agent_events(create_event_iterator(events), send_message)

    assert result.properties.state == "complete"
    assert result.properties.icon == "Bot"
    assert len(result.content_blocks) == 1
    assert result.text == "final output"


async def test_unknown_event():
    """Test handling of unknown event type."""
    send_message = MagicMock(side_effect=lambda message: message)
    initial_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],  # Initialize with empty content block
    )
    send_message.return_value = initial_message

    events = [{"event": "unknown_event", "data": {"some": "data"}}]

    result = await process_agent_events(create_event_iterator(events), send_message)

    # Should complete without error and maintain default state
    assert result.properties.state == "complete"
    # Content blocks should be empty but present
    assert len(result.content_blocks) == 1
    assert len(result.content_blocks[0].contents) == 0


# Additional tests for individual handler functions


async def test_handle_on_chain_start_with_input():
    """Test handle_on_chain_start with input."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {"event": "on_chain_start", "data": {"input": {"input": "test input", "chat_history": []}}}

    updated_message = handle_on_chain_start(event, agent_message)

    assert updated_message.properties.icon == "Bot"
    assert len(updated_message.content_blocks) == 1
    assert updated_message.content_blocks[0].title == "Agent Steps"


async def test_handle_on_chain_start_no_input():
    """Test handle_on_chain_start without input."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {"event": "on_chain_start", "data": {}}

    updated_message = handle_on_chain_start(event, agent_message)

    assert updated_message.properties.icon == "Bot"
    # Content blocks should be present but empty
    assert len(updated_message.content_blocks) == 1
    assert len(updated_message.content_blocks[0].contents) == 0


async def test_handle_on_chain_end_with_output():
    """Test handle_on_chain_end with output."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    output = AgentFinish(return_values={"output": "final output"}, log="test log")
    event = {"event": "on_chain_end", "data": {"output": output}}

    updated_message = handle_on_chain_end(event, agent_message)

    assert updated_message.properties.icon == "Bot"
    assert updated_message.properties.state == "complete"
    assert updated_message.text == "final output"


async def test_handle_on_chain_end_no_output():
    """Test handle_on_chain_end without output key in data."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {"event": "on_chain_end", "data": {}}

    updated_message = handle_on_chain_end(event, agent_message)

    assert updated_message.properties.icon == "Bot"
    assert updated_message.properties.state == "partial"
    assert updated_message.text == ""


async def test_handle_on_chain_end_empty_data():
    """Test handle_on_chain_end with empty data."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {"event": "on_chain_end", "data": {"output": None}}

    updated_message = handle_on_chain_end(event, agent_message)

    assert updated_message.properties.icon == "Bot"
    assert updated_message.properties.state == "partial"
    assert updated_message.text == ""


async def test_handle_on_chain_end_with_empty_return_values():
    """Test handle_on_chain_end with empty return_values."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    class MockOutputEmptyReturnValues:
        def __init__(self):
            self.return_values = {}

    event = {"event": "on_chain_end", "data": {"output": MockOutputEmptyReturnValues()}}

    updated_message = handle_on_chain_end(event, agent_message)

    assert updated_message.properties.icon == "Bot"
    assert updated_message.properties.state == "partial"
    assert updated_message.text == ""


def test_handle_on_tool_start():
    """Test handle_on_tool_start event."""
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
    }

    updated_message = handle_on_tool_start(event, agent_message, tool_blocks_map)

    assert len(updated_message.content_blocks) == 1
    assert len(updated_message.content_blocks[0].contents) > 0
    tool_content = updated_message.content_blocks[0].contents[-1]
    assert tool_content == tool_blocks_map.get("test_run")
    assert isinstance(tool_content, ToolContent)
    assert tool_content.name == "test_tool"
    assert tool_content.tool_input == {"query": "tool input"}, tool_content


async def test_handle_on_tool_end():
    """Test handle_on_tool_end event."""
    tool_blocks_map = {}
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    # First create a tool content with start event
    start_event = {
        "event": "on_tool_start",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"input": {"query": "tool input"}},
    }
    agent_message = handle_on_tool_start(start_event, agent_message, tool_blocks_map)

    # Then handle the end event
    end_event = {
        "event": "on_tool_end",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"output": "tool output"},
    }

    updated_message = handle_on_tool_end(end_event, agent_message, tool_blocks_map)

    tool_content = updated_message.content_blocks[0].contents[-1]
    assert tool_content.name == "test_tool"
    assert tool_content.output == "tool output"
    assert hasattr(tool_content, "duration")


async def test_handle_on_tool_error():
    """Test handle_on_tool_error event."""
    tool_blocks_map = {}
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )

    # First create a tool content with start event
    start_event = {
        "event": "on_tool_start",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"input": {"query": "tool input"}},
    }
    agent_message = handle_on_tool_start(start_event, agent_message, tool_blocks_map)

    # Then handle the error event
    error_event = {
        "event": "on_tool_error",
        "name": "test_tool",
        "run_id": "test_run",
        "data": {"error": "error message"},
    }

    updated_message = handle_on_tool_error(error_event, agent_message, tool_blocks_map)

    tool_content = updated_message.content_blocks[0].contents[-1]
    assert tool_content.name == "test_tool"
    assert tool_content.error == "error message"
    assert tool_content.header["title"] == "Error using **test_tool**"
    assert hasattr(tool_content, "duration")


async def test_handle_on_chain_stream_with_output():
    """Test handle_on_chain_stream with output."""
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

    updated_message = handle_on_chain_stream(event, agent_message)

    assert updated_message.text == "streamed output"
    assert updated_message.properties.state == "complete"


async def test_handle_on_chain_stream_no_output():
    """Test handle_on_chain_stream without output."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "Bot", "state": "partial"},
        content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
    )
    event = {
        "event": "on_chain_stream",
        "data": {"chunk": {}},
    }

    updated_message = handle_on_chain_stream(event, agent_message)

    assert updated_message.text == ""
    assert updated_message.properties.state == "partial"
