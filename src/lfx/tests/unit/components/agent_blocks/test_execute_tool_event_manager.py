"""Tests for ExecuteTool's _send_message_event method."""

from unittest.mock import MagicMock

import pytest
from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import ToolContent
from lfx.schema.message import Message


@pytest.mark.asyncio
async def test_send_message_event_includes_content_blocks():
    """Test that _send_message_event correctly passes content_blocks to event_manager.

    This verifies the actual method behavior, not mocked behavior.
    """
    captured_data = []

    mock_event_manager = MagicMock()
    mock_event_manager.on_message = MagicMock(side_effect=lambda data: captured_data.append(data))

    comp = ExecuteToolComponent()
    comp._event_manager = mock_event_manager

    # Create a message with content_blocks
    msg = Message(
        text="Test message",
        sender="Machine",
        sender_name="AI",
        content_blocks=[
            ContentBlock(
                title="Agent Steps",
                contents=[
                    ToolContent(
                        type="tool_use",
                        name="my_tool",
                        tool_input={"arg": "value"},
                        output="tool result",
                        header={"title": "Executed **my_tool**", "icon": "Hammer"},
                        duration=100,
                    )
                ],
            )
        ],
    )

    # Call the real _send_message_event
    await comp._send_message_event(msg)

    # Verify it was called
    assert mock_event_manager.on_message.called, "_send_message_event did not call on_message"

    # Check the data
    assert len(captured_data) == 1
    data = captured_data[0]

    # Verify content_blocks is present and correct
    assert "content_blocks" in data, "content_blocks not in event data"

    content_blocks = data["content_blocks"]
    assert len(content_blocks) == 1
    assert content_blocks[0]["title"] == "Agent Steps"
    assert len(content_blocks[0]["contents"]) == 1

    tool_content = content_blocks[0]["contents"][0]
    assert tool_content["type"] == "tool_use"
    assert tool_content["name"] == "my_tool"
    assert tool_content["output"] == "tool result"
