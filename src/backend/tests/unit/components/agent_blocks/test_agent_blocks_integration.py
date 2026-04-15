"""Integration tests for agent building blocks.

These tests verify the actual behavior of agent block components,
not mocked implementation details.
"""

from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message


class TestMessageIdExtraction:
    """Tests for message ID extraction from DataFrame."""

    def test_extract_from_accumulated_dataframe(self):
        """Test extracting message ID from accumulated DataFrame."""
        from langflow.base.agents.message_utils import extract_message_id_from_dataframe
        from langflow.base.agents.tool_execution import build_ai_message_row, build_tool_result_row

        # Build accumulated state like WhileLoop would
        initial = DataFrame([{"text": "Question", "sender": "User"}])
        ai_row = build_ai_message_row("Answer", [{"name": "t", "args": {}, "id": "c1"}], "the-message-id", None)
        tool_row = build_tool_result_row("t", "c1", result="result")

        accumulated = initial.add_rows([ai_row, tool_row])

        extracted = extract_message_id_from_dataframe(accumulated)
        assert extracted == "the-message-id"


class TestWhileLoopToDataframe:
    """Tests for WhileLoop._to_dataframe handling various inputs."""

    def test_list_preserves_columns(self):
        """List of dicts should preserve all columns including _agent_message_id."""
        from langflow.components.flow_controls.while_loop import WhileLoopComponent

        loop = WhileLoopComponent()
        input_list = [
            {"text": "AI response", "sender": "Machine", "_agent_message_id": "test-id", "tool_calls": []},
            {"text": "Tool result", "sender": "Tool", "_agent_message_id": None},
        ]

        result = loop._to_dataframe(input_list)

        assert "_agent_message_id" in result.columns
        assert result.iloc[0]["_agent_message_id"] == "test-id"


class TestShouldSkipMessagePriority:
    """Tests for _should_skip_message priority logic."""

    def test_stream_events_false_skips_even_with_stream_to_playground(self):
        """stream_events=False should take precedence over _stream_to_playground."""
        from unittest.mock import MagicMock

        from langflow.components.agent_blocks import AgentStepComponent

        component = AgentStepComponent()
        component.stream_events = False

        mock_graph = MagicMock()
        mock_graph._stream_to_playground = True

        mock_vertex = MagicMock()
        mock_vertex.is_output = False
        mock_vertex.is_input = False
        mock_vertex.graph = mock_graph
        component._vertex = mock_vertex

        message = Message(text="Test", sender="Machine")
        result = component._should_skip_message(message)

        assert result is True, "stream_events=False should skip message"
