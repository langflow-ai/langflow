"""Test that content_blocks are preserved through the agent loop.

This test specifically covers the bug where CallModel's second iteration
would send an add_message event with empty content_blocks, erasing the
tool execution steps that ExecuteTool had added.
"""

from lfx.base.agents.message_utils import extract_content_blocks_from_dataframe
from lfx.base.agents.tool_execution import build_ai_message_row
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import ToolContent
from lfx.schema.dataframe import DataFrame


class TestContentBlocksPreservation:
    """Tests for content_blocks preservation through DataFrame."""

    def test_build_ai_message_row_includes_content_blocks(self):
        """Test that build_ai_message_row includes content_blocks in the row."""
        content_blocks = [
            ContentBlock(
                title="Agent Steps",
                contents=[
                    ToolContent(
                        type="tool_use",
                        name="search",
                        tool_input={"query": "test"},
                        output="Search results",
                        header={"title": "Executed **search**", "icon": "Hammer"},
                        duration=100,
                    )
                ],
            )
        ]

        row = build_ai_message_row(
            text="Let me search",
            tool_calls=[{"name": "search", "args": {"query": "test"}, "id": "call_1"}],
            message_id="msg_123",
            content_blocks=content_blocks,
        )

        assert row["_agent_content_blocks"] == content_blocks
        assert row["_agent_message_id"] == "msg_123"

    def test_extract_content_blocks_from_dataframe(self):
        """Test that content_blocks can be extracted from DataFrame."""
        content_blocks = [
            ContentBlock(
                title="Agent Steps",
                contents=[
                    ToolContent(
                        type="tool_use",
                        name="fetch",
                        tool_input={"url": "https://example.com"},
                        output="Page content",
                        header={"title": "Executed **fetch**", "icon": "Hammer"},
                        duration=200,
                    )
                ],
            )
        ]

        df = DataFrame(
            [
                {
                    "text": "User message",
                    "sender": "User",
                    "_agent_content_blocks": None,
                },
                {
                    "text": "AI message",
                    "sender": "Machine",
                    "_agent_content_blocks": content_blocks,
                },
                {
                    "text": "Tool result",
                    "sender": "Tool",
                    "_agent_content_blocks": None,
                },
            ]
        )

        extracted = extract_content_blocks_from_dataframe(df)

        assert extracted == content_blocks
        assert len(extracted) == 1
        assert extracted[0].title == "Agent Steps"
        assert extracted[0].contents[0].name == "fetch"

    def test_extract_content_blocks_returns_none_when_not_present(self):
        """Test that extraction returns None when no content_blocks in DataFrame."""
        df = DataFrame(
            [
                {"text": "Hello", "sender": "User"},
                {"text": "Hi", "sender": "Machine"},
            ]
        )

        extracted = extract_content_blocks_from_dataframe(df)

        assert extracted is None

    def test_content_blocks_roundtrip_through_dataframe(self):
        """Test the full roundtrip: build row -> DataFrame -> extract.

        This simulates what happens in the agent loop:
        1. ExecuteTool builds AI message row with content_blocks
        2. DataFrame is created and passed through WhileLoop
        3. CallModel extracts content_blocks from DataFrame
        """
        # Simulate ExecuteTool building the row with content_blocks
        original_content_blocks = [
            ContentBlock(
                title="Agent Steps",
                contents=[
                    ToolContent(
                        type="tool_use",
                        name="calculator",
                        tool_input={"expression": "2+2"},
                        output="4",
                        header={"title": "Executed **calculator**", "icon": "Calculator"},
                        duration=50,
                    ),
                    ToolContent(
                        type="tool_use",
                        name="search",
                        tool_input={"query": "python"},
                        output="Python is a programming language",
                        header={"title": "Executed **search**", "icon": "Search"},
                        duration=150,
                    ),
                ],
            )
        ]

        ai_row = build_ai_message_row(
            text="Let me help",
            tool_calls=[
                {"name": "calculator", "args": {"expression": "2+2"}, "id": "call_1"},
                {"name": "search", "args": {"query": "python"}, "id": "call_2"},
            ],
            message_id="msg_abc",
            content_blocks=original_content_blocks,
        )

        tool_result_rows = [
            {
                "text": "4",
                "sender": "Tool",
                "tool_call_id": "call_1",
                "is_tool_result": True,
            },
            {
                "text": "Python is a programming language",
                "sender": "Tool",
                "tool_call_id": "call_2",
                "is_tool_result": True,
            },
        ]

        # Create DataFrame like WhileLoop would
        df = DataFrame([ai_row, *tool_result_rows])

        # Extract like CallModel would
        extracted_content_blocks = extract_content_blocks_from_dataframe(df)

        # Verify content_blocks were preserved
        assert extracted_content_blocks is not None
        assert len(extracted_content_blocks) == 1
        assert extracted_content_blocks[0].title == "Agent Steps"
        assert len(extracted_content_blocks[0].contents) == 2
        assert extracted_content_blocks[0].contents[0].name == "calculator"
        assert extracted_content_blocks[0].contents[1].name == "search"
