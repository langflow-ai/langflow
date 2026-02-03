"""Integration tests for agent blocks - CallModel + ExecuteTool."""

import uuid

import pytest
from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
from lfx.events.event_manager import EventManager
from lfx.schema.message import Message


class MockTool:
    """A mock tool for testing."""

    name = "search"
    description = "Search for information"

    async def ainvoke(self, args):
        return f"Search results for: {args.get('query', 'unknown')}"


def create_mock_event_manager():
    """Create a mock event manager that captures all events."""
    captured_events = []

    class MockQueue:
        def put_nowait(self, item):
            import json

            _event_id, data_bytes, _timestamp = item
            data = json.loads(data_bytes.decode("utf-8").strip())
            captured_events.append(data)

    manager = EventManager(MockQueue())
    manager.register_event("on_token", "token")
    manager.register_event("on_message", "add_message")
    manager.register_event("on_end", "end")
    manager.register_event("on_end_vertex", "end_vertex")

    return manager, captured_events


@pytest.mark.asyncio
async def test_execute_tool_with_event_manager_integration():
    """Test ExecuteTool with a real-ish event manager.

    This test verifies that ExecuteTool correctly uses _send_tool_event
    to bypass the _should_skip_message check and always emit events.
    """
    event_manager, captured_events = create_mock_event_manager()

    # Create ExecuteTool component
    comp = ExecuteToolComponent()
    comp._event_manager = event_manager
    comp._vertex = None  # No vertex
    comp.tools = [MockTool()]

    # Create AI message with tool calls (simulating output from CallModel)
    session_id = str(uuid.uuid4())
    ai_message = Message(
        text="Let me search for that.",
        sender="Machine",
        sender_name="AI",
        id="msg_from_call_model",
        session_id=session_id,
    )
    ai_message.data["tool_calls"] = [{"name": "search", "args": {"query": "test query"}, "id": "call_123"}]
    comp.tool_calls_message = ai_message

    # Execute
    await comp.execute_tools()

    # Verify add_message events were sent
    add_message_events = [e for e in captured_events if e.get("event") == "add_message"]
    assert len(add_message_events) > 0, "No add_message events were captured"

    # Find events with tool content
    events_with_tools = []
    for event in add_message_events:
        data = event.get("data", {})
        content_blocks = data.get("content_blocks", [])
        for block in content_blocks:
            for content in block.get("contents", []):
                if content.get("type") == "tool_use":
                    events_with_tools.append(event)
                    break

    assert len(events_with_tools) > 0, "No events with tool_use content found"

    # Verify tool output was set
    last_tool_event = events_with_tools[-1]
    tool_content = last_tool_event["data"]["content_blocks"][0]["contents"][0]
    assert tool_content["output"] is not None, "Tool output should be set"
    assert "Search results" in tool_content["output"]


@pytest.mark.asyncio
async def test_execute_tool_sends_events_when_should_stream_events_true():
    """Test that ExecuteTool sends events when should_stream_events flag is True.

    CallModel passes should_stream_events=True when the agent flow is connected
    to a ChatOutput. ExecuteTool should then send tool execution events.
    """
    from unittest.mock import MagicMock

    event_manager, captured_events = create_mock_event_manager()

    # Create a mock vertex with graph = None to avoid MagicMock issues
    mock_vertex = MagicMock()
    mock_vertex.graph = None

    comp = ExecuteToolComponent()
    comp._event_manager = event_manager
    comp._vertex = mock_vertex
    comp.tools = [MockTool()]
    # Set session_id directly to avoid graph lookup issues
    comp._session_id = str(uuid.uuid4())

    session_id = str(uuid.uuid4())
    ai_message = Message(
        text="Test",
        sender="Machine",
        sender_name="AI",
        id="msg_123",
        session_id=session_id,
    )
    ai_message.data["tool_calls"] = [{"name": "search", "args": {"query": "test"}, "id": "call_1"}]
    # CallModel sets this flag when connected to ChatOutput
    ai_message.data["should_stream_events"] = True
    comp.tool_calls_message = ai_message

    await comp.execute_tools()

    add_message_events = [e for e in captured_events if e.get("event") == "add_message"]

    # Events should be sent when should_stream_events is True
    assert len(add_message_events) > 0, "Events should be sent when should_stream_events=True"

    # Verify tool content is in the events
    has_tool_content = False
    for event in add_message_events:
        for block in event.get("data", {}).get("content_blocks", []):
            for content in block.get("contents", []):
                if content.get("type") == "tool_use":
                    has_tool_content = True
                    break

    assert has_tool_content, "Tool content should be in events"


@pytest.mark.asyncio
async def test_execute_tool_skips_events_when_should_stream_events_false():
    """Test that ExecuteTool skips events when should_stream_events flag is False.

    CallModel passes should_stream_events=False when the agent flow is NOT connected
    to a ChatOutput (e.g., when the agent is used as a tool). ExecuteTool should
    skip events to avoid flooding the UI.
    """
    from unittest.mock import MagicMock

    event_manager, captured_events = create_mock_event_manager()

    # Create a mock vertex with graph = None to avoid MagicMock issues
    mock_vertex = MagicMock()
    mock_vertex.graph = None

    comp = ExecuteToolComponent()
    comp._event_manager = event_manager
    comp._vertex = mock_vertex
    comp.tools = [MockTool()]
    # Set session_id directly to avoid graph lookup issues
    comp._session_id = str(uuid.uuid4())

    session_id = str(uuid.uuid4())
    ai_message = Message(
        text="Test",
        sender="Machine",
        sender_name="AI",
        id="msg_123",
        session_id=session_id,
    )
    ai_message.data["tool_calls"] = [{"name": "search", "args": {"query": "test"}, "id": "call_1"}]
    # CallModel sets this flag to False when NOT connected to ChatOutput (nested agent)
    ai_message.data["should_stream_events"] = False
    comp.tool_calls_message = ai_message

    await comp.execute_tools()

    add_message_events = [e for e in captured_events if e.get("event") == "add_message"]

    # Events should be SKIPPED when should_stream_events is False
    # This prevents nested agents from flooding the UI
    assert len(add_message_events) == 0, "Events should be skipped when should_stream_events=False"


@pytest.mark.asyncio
async def test_execute_tool_emits_tool_lifecycle_events():
    """Test that ExecuteTool emits events for tool start and tool end."""
    event_manager, captured_events = create_mock_event_manager()

    comp = ExecuteToolComponent()
    comp._event_manager = event_manager
    comp._vertex = None
    comp.tools = [MockTool()]

    session_id = str(uuid.uuid4())
    ai_message = Message(
        text="Test",
        sender="Machine",
        sender_name="AI",
        id="msg_123",
        session_id=session_id,
    )
    ai_message.data["tool_calls"] = [{"name": "search", "args": {"query": "test"}, "id": "call_1"}]
    comp.tool_calls_message = ai_message

    await comp.execute_tools()

    add_message_events = [e for e in captured_events if e.get("event") == "add_message"]

    # Should have multiple events for tool lifecycle
    assert len(add_message_events) >= 3, f"Expected at least 3 events, got {len(add_message_events)}"

    # Find tool start and end events
    tool_start_found = False
    tool_end_found = False

    for event in add_message_events:
        for block in event.get("data", {}).get("content_blocks", []):
            for content in block.get("contents", []):
                if content.get("type") == "tool_use":
                    if content.get("output") is None:
                        tool_start_found = True
                    else:
                        tool_end_found = True

    assert tool_start_found, "No tool start event found (tool_use with output=None)"
    assert tool_end_found, "No tool end event found (tool_use with output set)"
