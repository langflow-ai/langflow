import asyncio
import time
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langflow.events.event_manager import EventManager
from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import TextContent, ToolContent
from langflow.schema.message import Message
from langflow.schema.properties import Properties, Source
from langflow.template.field.base import Output

from lfx.custom.custom_component.component import Component


def blocking_cb(manager, event_type, data):
    time.sleep(0.01)
    manager.send_event(event_type=event_type, data=data)


class ComponentForTesting(Component):
    """Test component that implements basic functionality."""

    def build(self) -> None:
        pass

    def get_text(self) -> str:
        """Return a simple text output."""
        return "test output"

    def get_tool(self) -> dict[str, Any]:
        """Return a tool output."""
        return {"name": "test_tool", "description": "A test tool"}


@pytest.mark.usefixtures("client")
async def test_component_message_sending():
    """Test component's message sending functionality."""
    # Create event queue and manager
    queue = asyncio.Queue()
    event_manager = EventManager(queue)

    event_manager.register_event("on_message", "message", callback=blocking_cb)

    # Create component
    component = ComponentForTesting()
    component.set_event_manager(event_manager)

    # Create a message
    properties = Properties()
    message = Message(
        sender="test_sender",
        session_id="test_session",
        sender_name="test_sender_name",
        content_blocks=[ContentBlock(title="Test Block", contents=[TextContent(type="text", text="Test message")])],
        properties=properties,
    )

    # Send the message
    sent_message = await component.send_message(message)

    # Verify the message was sent
    assert sent_message.id is not None
    assert len(sent_message.content_blocks) == 1
    assert isinstance(sent_message.content_blocks[0].contents[0], TextContent)


@pytest.mark.usefixtures("client")
async def test_component_tool_output():
    """Test component's tool output functionality."""
    # Create event queue and manager
    queue = asyncio.Queue()
    event_manager = EventManager(queue)

    # Create component
    component = ComponentForTesting()
    component.set_event_manager(event_manager)

    # Create a message with tool content
    properties = Properties()
    message = Message(
        sender="test_sender",
        session_id="test_session",
        sender_name="test_sender_name",
        content_blocks=[
            ContentBlock(
                title="Tool Output",
                contents=[ToolContent(type="tool_use", name="test_tool", tool_input={"query": "test input"})],
            )
        ],
        properties=properties,
    )

    # Send the message
    sent_message = await component.send_message(message)

    # Verify the message was stored and processed
    assert sent_message.id is not None
    assert len(sent_message.content_blocks) == 1
    assert isinstance(sent_message.content_blocks[0].contents[0], ToolContent)


@pytest.mark.usefixtures("client")
async def test_component_error_handling():
    """Test component's error handling."""
    # Create event queue and manager
    queue = asyncio.Queue()
    event_manager = EventManager(queue)

    # Create component
    component = ComponentForTesting()
    component.set_event_manager(event_manager)

    # Trigger an error
    class CustomError(Exception):
        pass

    try:
        msg = "Test error"
        raise CustomError(msg)
    except CustomError as e:
        sent_message = await component.send_error(
            exception=e,
            session_id="test_session",
            trace_name="test_trace",
            source=Source(id="test_id", display_name="Test Component", source="Test Component"),
        )

    # Verify error message
    assert sent_message is not None
    assert "Test error" in str(sent_message.text)


@pytest.mark.usefixtures("client")
async def test_component_build_results():
    """Test that build_results correctly generates output results and artifacts for defined outputs.

    Test that the results dictionary contains the correct output keys and values,
    and that the artifacts dictionary includes the correct types for each output.
    """
    # Create event queue and manager
    queue = asyncio.Queue()
    event_manager = EventManager(queue)

    # Create component
    component = ComponentForTesting()
    component.set_event_manager(event_manager)

    # Add outputs to the component
    component._outputs_map = {
        "text_output": Output(name="text_output", method="get_text"),
        "tool_output": Output(name="tool_output", method="get_tool"),
    }

    component.outputs = [
        Output(name="text_output", method="get_text"),
        Output(name="tool_output", method="get_tool"),
    ]

    # Build results
    results, artifacts = await component._build_results()

    # Verify results
    assert "text_output" in results
    assert results["text_output"] == "test output"
    assert "tool_output" in results
    assert results["tool_output"]["name"] == "test_tool"

    # Verify artifacts
    assert "text_output" in artifacts
    assert "tool_output" in artifacts
    assert artifacts["text_output"]["type"] == "text"


@pytest.mark.usefixtures("client")
async def test_component_logging():
    """Test component's logging functionality."""
    # Create event queue and manager
    queue = asyncio.Queue()
    event_manager = EventManager(queue)

    # Create component
    component = ComponentForTesting()
    component.set_event_manager(event_manager)

    # Set current output (required for logging)
    component._current_output = "test_output"
    component._id = "test_component_id"  # Set component ID

    # Create a custom callback for logging
    def log_callback(*, manager: EventManager, event_type: str, data: dict):  # noqa: ARG001
        manager.send_event(
            event_type="info", data={"message": data["message"], "id": data.get("component_id", "test_id")}
        )

    # Register the log event with custom callback
    event_manager.register_event("on_log", "info", callback=log_callback)

    # Log a message
    await asyncio.to_thread(component.log, "Test log message")

    # Get the event from the queue
    event_id, event_data, _ = queue.get_nowait()
    event = event_data.decode("utf-8")

    assert "Test log message" in event
    assert event_id.startswith("info-")


@pytest.mark.usefixtures("client")
async def test_component_streaming_message():
    """Test component's streaming message functionality."""
    queue = asyncio.Queue()
    event_manager = EventManager(queue)

    event_manager.register_event("on_token", "token", blocking_cb)

    # Create a proper mock vertex with graph and flow_id
    vertex = MagicMock()
    mock_graph = MagicMock()
    mock_graph.flow_id = str(uuid4())
    vertex.graph = mock_graph

    component = ComponentForTesting(_vertex=vertex)
    component.set_event_manager(event_manager)

    # Create a chunk class that mimics LangChain's streaming format
    class StreamChunk:
        def __init__(self, content: str):
            self.content = content

    async def text_generator():
        chunks = ["Hello", " ", "World", "!"]
        for chunk in chunks:
            yield StreamChunk(chunk)

    # Create a streaming message
    properties = Properties()
    message = Message(
        sender="test_sender",
        session_id="test_session",
        sender_name="test_sender_name",
        text=text_generator(),
        properties=properties,
    )

    # Send the streaming message
    sent_message = await component.send_message(message)

    # Verify the message
    assert sent_message.id is not None
    assert sent_message.text == "Hello World!"

    # Check tokens in queue
    tokens = []
    while not queue.empty():
        _, event_data, _ = queue.get_nowait()
        event = event_data.decode("utf-8")
        if "token" in event:
            tokens.append(event)

    assert len(tokens) > 0
