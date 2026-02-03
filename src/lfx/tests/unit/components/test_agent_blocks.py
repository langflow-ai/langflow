"""Tests for agent building block components.

These tests focus on actual behavior, not mocked implementation details.
"""

import pytest
from lfx.components.agent_blocks import (
    AgentStepComponent,
    ExecuteToolComponent,
    ThinkToolComponent,
)
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class TestComponentInstantiation:
    """Basic instantiation tests - these are fine as sanity checks."""

    def test_agent_step_instantiation(self):
        comp = AgentStepComponent()
        assert comp.display_name == "Agent Step"
        assert "messages" in [i.name for i in comp.inputs]
        assert "ai_message" in [o.name for o in comp.outputs]
        assert "tool_calls" in [o.name for o in comp.outputs]

    def test_execute_tool_instantiation(self):
        comp = ExecuteToolComponent()
        assert comp.display_name == "Execute Tool"
        assert "tool_calls_message" in [i.name for i in comp.inputs]
        assert "messages" in [o.name for o in comp.outputs]

    def test_think_tool_builds(self):
        comp = ThinkToolComponent()
        tool = comp.build_tool()
        assert tool.name == "think"


class TestMessageConversion:
    """Tests for AgentStep's message conversion - tests real behavior."""

    def test_user_message_becomes_human_message(self):
        comp = AgentStepComponent()
        df = DataFrame([{"text": "Hello", "sender": "User"}])
        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].__class__.__name__ == "HumanMessage"
        assert lc_messages[0].content == "Hello"

    def test_machine_message_becomes_ai_message(self):
        comp = AgentStepComponent()
        df = DataFrame([{"text": "Hi there", "sender": "Machine"}])
        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].__class__.__name__ == "AIMessage"

    def test_tool_result_becomes_tool_message(self):
        comp = AgentStepComponent()
        df = DataFrame([{"text": "42", "is_tool_result": True, "tool_call_id": "call_123"}])
        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].__class__.__name__ == "ToolMessage"
        assert lc_messages[0].tool_call_id == "call_123"

    def test_ai_message_with_tool_calls(self):
        comp = AgentStepComponent()
        df = DataFrame(
            [
                {
                    "text": "Let me calculate",
                    "sender": "Machine",
                    "tool_calls": [{"name": "calc", "args": {"x": 5}, "id": "call_1"}],
                }
            ]
        )
        lc_messages = comp._convert_to_lc_messages(df)

        assert lc_messages[0].tool_calls == [{"name": "calc", "args": {"x": 5}, "id": "call_1"}]

    def test_full_conversation(self):
        comp = AgentStepComponent()
        df = DataFrame(
            [
                {"text": "What is 2+2?", "sender": "User"},
                {
                    "text": "Let me calculate",
                    "sender": "Machine",
                    "tool_calls": [{"name": "calc", "args": {}, "id": "c1"}],
                },
                {"text": "4", "is_tool_result": True, "tool_call_id": "c1"},
            ]
        )
        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 3
        assert [m.__class__.__name__ for m in lc_messages] == ["HumanMessage", "AIMessage", "ToolMessage"]


class TestWhileLoopToDataframe:
    """Tests for WhileLoop._to_dataframe - THIS WOULD HAVE CAUGHT THE BUG."""

    def test_list_of_dicts_preserves_all_columns(self):
        """The actual bug: _to_dataframe didn't handle lists, losing _agent_message_id."""
        from lfx.components.flow_controls.while_loop import WhileLoopComponent

        loop = WhileLoopComponent()

        # This is what ExecuteTool returns - a list of dicts
        input_list = [
            {"text": "AI response", "sender": "Machine", "_agent_message_id": "test-id-123", "tool_calls": []},
            {"text": "Tool result", "sender": "Tool", "_agent_message_id": None, "tool_call_id": "call_1"},
        ]

        result = loop._to_dataframe(input_list)

        # THIS ASSERTION WOULD HAVE FAILED BEFORE THE FIX
        assert "_agent_message_id" in result.columns, "List conversion must preserve _agent_message_id column"
        assert result.iloc[0]["_agent_message_id"] == "test-id-123"

    def test_dataframe_passes_through(self):
        from lfx.components.flow_controls.while_loop import WhileLoopComponent

        loop = WhileLoopComponent()
        df = DataFrame([{"text": "test", "custom_col": "value"}])

        result = loop._to_dataframe(df)

        assert "custom_col" in result.columns
        assert result.iloc[0]["custom_col"] == "value"

    def test_message_converts_to_dataframe(self):
        from lfx.components.flow_controls.while_loop import WhileLoopComponent

        loop = WhileLoopComponent()
        msg = Message(text="Hello", sender="User")

        result = loop._to_dataframe(msg)

        assert isinstance(result, DataFrame)
        assert result.iloc[0]["text"] == "Hello"


class TestDataFrameAccumulation:
    """Tests for DataFrame.add_rows preserving columns - tests actual DataFrame behavior."""

    def test_add_rows_preserves_new_columns(self):
        """When adding rows with new columns, those columns should exist in result."""
        initial = DataFrame([{"text": "Hello", "sender": "User"}])

        new_rows = [
            {"text": "Response", "sender": "Machine", "_agent_message_id": "test-id"},
        ]
        accumulated = initial.add_rows(new_rows)

        assert "_agent_message_id" in accumulated.columns
        assert accumulated.iloc[1]["_agent_message_id"] == "test-id"

    def test_accumulated_state_has_all_columns(self):
        """Simulate WhileLoop accumulation - verify columns from both sources exist."""
        from lfx.base.agents.tool_execution import build_ai_message_row, build_tool_result_row

        initial_state = DataFrame([{"text": "What time is it?", "sender": "User"}])

        ai_row = build_ai_message_row(
            text="Let me check",
            tool_calls=[{"name": "get_time", "args": {}, "id": "call_1"}],
            message_id="msg-id-123",
            content_blocks=None,
        )
        tool_row = build_tool_result_row("get_time", "call_1", result="14:30")

        new_rows = [ai_row, tool_row]
        accumulated = initial_state.add_rows(new_rows)

        # These columns come from build_ai_message_row
        assert "_agent_message_id" in accumulated.columns
        assert "tool_calls" in accumulated.columns
        assert "has_tool_calls" in accumulated.columns


class TestMessageIdExtraction:
    """Tests for extracting message ID from DataFrame."""

    def test_extract_finds_id_in_accumulated_dataframe(self):
        """Extract ID from a DataFrame that has been through accumulation."""
        from lfx.base.agents.message_utils import extract_message_id_from_dataframe
        from lfx.base.agents.tool_execution import build_ai_message_row, build_tool_result_row

        # Build accumulated state like WhileLoop would
        initial = DataFrame([{"text": "Question", "sender": "User"}])
        ai_row = build_ai_message_row("Answer", [{"name": "t", "args": {}, "id": "c1"}], "the-message-id", None)
        tool_row = build_tool_result_row("t", "c1", result="result")

        accumulated = initial.add_rows([ai_row, tool_row])

        extracted = extract_message_id_from_dataframe(accumulated)
        assert extracted == "the-message-id"

    def test_extract_skips_nan_values(self):
        """Tool result rows have NaN for _agent_message_id - should be skipped."""
        from lfx.base.agents.message_utils import extract_message_id_from_dataframe

        df = DataFrame(
            [
                {"text": "User msg", "sender": "User"},  # No _agent_message_id
                {"text": "AI msg", "sender": "Machine", "_agent_message_id": "valid-id"},
                {"text": "Tool result", "sender": "Tool", "_agent_message_id": float("nan")},  # NaN
            ]
        )

        extracted = extract_message_id_from_dataframe(df)
        assert extracted == "valid-id"


class TestShouldSkipMessagePriority:
    """Tests for _should_skip_message priority - THIS WOULD HAVE CAUGHT THE BUG."""

    def test_stream_events_false_takes_precedence(self):
        """When stream_events=False, messages should be skipped regardless of _stream_to_playground."""
        from unittest.mock import MagicMock

        component = AgentStepComponent()
        component.stream_events = False  # Component explicitly disabled streaming

        # Mock graph WITH _stream_to_playground=True
        mock_graph = MagicMock()
        mock_graph._stream_to_playground = True

        mock_vertex = MagicMock()
        mock_vertex.is_output = False
        mock_vertex.is_input = False
        mock_vertex.graph = mock_graph
        component._vertex = mock_vertex

        message = Message(text="Test", sender="Machine")

        # THIS ASSERTION WOULD HAVE FAILED BEFORE THE FIX
        # stream_events=False should take precedence over _stream_to_playground
        result = component._should_skip_message(message)
        assert result is True, "stream_events=False should skip message even with _stream_to_playground=True"

    def test_stream_to_playground_allows_storage_when_stream_events_true(self):
        """When stream_events=True and _stream_to_playground=True, messages should NOT be skipped."""
        from unittest.mock import MagicMock

        component = AgentStepComponent()
        component.stream_events = True  # Default

        mock_graph = MagicMock()
        mock_graph._stream_to_playground = True

        mock_vertex = MagicMock()
        mock_vertex.is_output = False
        mock_vertex.is_input = False
        mock_vertex.graph = mock_graph
        component._vertex = mock_vertex

        message = Message(text="Test", sender="Machine")

        result = component._should_skip_message(message)
        assert result is False, "Should NOT skip when stream_events=True and _stream_to_playground=True"


class TestBuildAiMessageRow:
    """Tests for build_ai_message_row - tests actual output structure."""

    def test_includes_agent_message_id(self):
        from lfx.base.agents.tool_execution import build_ai_message_row

        row = build_ai_message_row(
            text="Response",
            tool_calls=[{"name": "test", "args": {}, "id": "c1"}],
            message_id="msg-123",
            content_blocks=None,
        )

        assert row["_agent_message_id"] == "msg-123"
        assert row["has_tool_calls"] is True
        assert row["sender"] == "Machine"

    def test_handles_none_message_id(self):
        from lfx.base.agents.tool_execution import build_ai_message_row

        row = build_ai_message_row(
            text="Response",
            tool_calls=[],
            message_id=None,
            content_blocks=None,
        )

        assert row["_agent_message_id"] is None


class TestMessageHasId:
    """Tests for Message.has_id() - tests actual Message behavior."""

    def test_has_id_false_when_no_id(self):
        message = Message(text="Test", sender="User")
        assert not message.has_id()

    def test_has_id_true_when_set(self):
        message = Message(text="Test", sender="User")
        message.id = "test-id"
        assert message.has_id()

    def test_has_id_true_when_in_data(self):
        message = Message(text="Test", sender="User", data={"id": "test-id"})
        assert message.has_id()

    def test_has_id_false_when_none(self):
        message = Message(text="Test", sender="User", data={"id": None})
        assert not message.has_id()


class TestUUIDConversion:
    """Tests for UUID string/object conversion - THIS WOULD HAVE CAUGHT THE BUG."""

    @pytest.mark.asyncio
    async def test_aupdate_messages_handles_string_id(self):
        """aupdate_messages should handle string IDs (from DataFrame) by converting to UUID."""
        import contextlib
        from unittest.mock import AsyncMock, patch
        from uuid import UUID

        # Create a message with string ID (as it would come from DataFrame)
        message = Message(text="Test", sender="Machine", sender_name="AI", session_id="test")
        message.id = "9a155de9-ad61-4e47-be05-7012557ff8d9"  # String, not UUID

        # Mock the session to verify UUID is used
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)  # Message not found (for this test)

        with patch("lfx.memory.stubs.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock(return_value=None)

            from lfx.memory.stubs import aupdate_messages

            with contextlib.suppress(ValueError):
                await aupdate_messages(message)

            # Verify message.id was converted to UUID
            assert isinstance(message.id, UUID), "String ID should be converted to UUID"


class TestWhileLoopBuildInitialState:
    """Tests for WhileLoop._build_initial_state - tests actual behavior."""

    def test_message_input_converts_to_dataframe(self):
        from lfx.components.flow_controls.while_loop import WhileLoopComponent

        loop = WhileLoopComponent()
        loop.input_value = Message(text="Hello", sender="User")
        loop.initial_state = None

        result = loop._build_initial_state()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["text"] == "Hello"

    def test_initial_state_prepended(self):
        from lfx.components.flow_controls.while_loop import WhileLoopComponent

        loop = WhileLoopComponent()
        loop.initial_state = DataFrame(
            [
                {"text": "History 1", "sender": "User"},
                {"text": "History 2", "sender": "Machine"},
            ]
        )
        loop.input_value = Message(text="Current", sender="User")

        result = loop._build_initial_state()

        assert len(result) == 3
        assert result.iloc[0]["text"] == "History 1"
        assert result.iloc[2]["text"] == "Current"
