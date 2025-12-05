"""Tests for lfx.base.agents.message_utils module."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from lfx.base.agents.message_utils import (
    convert_to_lc_messages,
    dataframe_to_lc_messages,
    extract_message_id_from_dataframe,
    messages_to_lc_messages,
    sanitize_tool_calls,
)
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class TestSanitizeToolCalls:
    """Tests for sanitize_tool_calls function."""

    def test_filters_empty_names(self):
        """Test that tool_calls with empty names are filtered out."""
        tool_calls = [
            {"name": "search", "args": {"q": "test"}, "id": "call_1"},
            {"name": "", "args": {}, "id": "call_2"},  # Should be filtered
            {"name": "calc", "args": {"x": 5}, "id": "call_3"},
        ]

        result = sanitize_tool_calls(tool_calls)

        assert len(result) == 2
        assert result[0]["name"] == "search"
        assert result[1]["name"] == "calc"

    def test_filters_missing_names(self):
        """Test that tool_calls without name key are filtered out."""
        tool_calls = [
            {"name": "search", "args": {}, "id": "call_1"},
            {"args": {}, "id": "call_2"},  # No name - should be filtered
        ]

        result = sanitize_tool_calls(tool_calls)

        assert len(result) == 1
        assert result[0]["name"] == "search"

    def test_generates_id_if_missing(self):
        """Test that missing IDs are generated."""
        tool_calls = [
            {"name": "search", "args": {}, "id": ""},
            {"name": "calc", "args": {}},  # No id at all
        ]

        result = sanitize_tool_calls(tool_calls)

        assert len(result) == 2
        assert result[0]["id"].startswith("call_")
        assert result[1]["id"].startswith("call_")

    def test_preserves_valid_tool_calls(self):
        """Test that valid tool_calls are preserved unchanged."""
        tool_calls = [
            {"name": "search", "args": {"q": "test"}, "id": "call_abc"},
        ]

        result = sanitize_tool_calls(tool_calls)

        assert len(result) == 1
        assert result[0]["name"] == "search"
        assert result[0]["args"] == {"q": "test"}
        assert result[0]["id"] == "call_abc"

    def test_handles_empty_list(self):
        """Test that empty list returns empty list."""
        result = sanitize_tool_calls([])
        assert result == []


class TestExtractMessageIdFromDataframe:
    """Tests for extract_message_id_from_dataframe function."""

    def test_extracts_valid_id(self):
        """Test extracting a valid message ID from DataFrame."""
        df = DataFrame(
            [
                {"text": "Hello", "sender": "User"},
                {"text": "Let me search", "sender": "Machine", "_agent_message_id": "msg_123"},
            ]
        )

        result = extract_message_id_from_dataframe(df)

        assert result == "msg_123"

    def test_returns_none_for_no_id(self):
        """Test that None is returned when no ID is present."""
        df = DataFrame(
            [
                {"text": "Hello", "sender": "User"},
                {"text": "Hi", "sender": "Machine"},
            ]
        )

        result = extract_message_id_from_dataframe(df)

        assert result is None

    def test_skips_nan_values(self):
        """Test that NaN values are skipped."""
        df = DataFrame(
            [
                {"text": "Hello", "sender": "User", "_agent_message_id": float("nan")},
                {"text": "Hi", "sender": "Machine", "_agent_message_id": "msg_456"},
            ]
        )

        result = extract_message_id_from_dataframe(df)

        assert result == "msg_456"

    def test_skips_none_values(self):
        """Test that None values are skipped."""
        df = DataFrame(
            [
                {"text": "Hello", "sender": "User", "_agent_message_id": None},
                {"text": "Hi", "sender": "Machine", "_agent_message_id": "msg_789"},
            ]
        )

        result = extract_message_id_from_dataframe(df)

        assert result == "msg_789"


class TestDataframeToLcMessages:
    """Tests for dataframe_to_lc_messages function."""

    def test_converts_user_message(self):
        """Test converting user message to HumanMessage."""
        df = DataFrame([{"text": "Hello", "sender": "User"}])

        result = dataframe_to_lc_messages(df)

        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "Hello"

    def test_converts_ai_message(self):
        """Test converting AI message to AIMessage."""
        df = DataFrame([{"text": "Hi there!", "sender": "Machine"}])

        result = dataframe_to_lc_messages(df)

        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "Hi there!"

    def test_converts_system_message(self):
        """Test converting system message to SystemMessage."""
        df = DataFrame([{"text": "Be helpful", "sender": "System"}])

        result = dataframe_to_lc_messages(df)

        assert len(result) == 1
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "Be helpful"

    def test_converts_tool_result(self):
        """Test converting tool result to ToolMessage."""
        df = DataFrame(
            [
                {
                    "text": "42",
                    "is_tool_result": True,
                    "tool_call_id": "call_123",
                }
            ]
        )

        result = dataframe_to_lc_messages(df)

        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert result[0].content == "42"
        assert result[0].tool_call_id == "call_123"

    def test_converts_ai_message_with_tool_calls(self):
        """Test converting AI message with tool_calls."""
        df = DataFrame(
            [
                {
                    "text": "Let me search",
                    "sender": "Machine",
                    "tool_calls": [{"name": "search", "args": {"q": "test"}, "id": "call_1"}],
                }
            ]
        )

        result = dataframe_to_lc_messages(df)

        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "Let me search"
        assert len(result[0].tool_calls) == 1
        assert result[0].tool_calls[0]["name"] == "search"

    def test_converts_full_conversation(self):
        """Test converting a full conversation DataFrame."""
        df = DataFrame(
            [
                {"text": "What is 2+2?", "sender": "User"},
                {
                    "text": "Let me calculate",
                    "sender": "Machine",
                    "tool_calls": [{"name": "calc", "args": {}, "id": "call_1"}],
                },
                {"text": "4", "is_tool_result": True, "tool_call_id": "call_1"},
                {"text": "The answer is 4", "sender": "Machine"},
            ]
        )

        result = dataframe_to_lc_messages(df)

        assert len(result) == 4
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], ToolMessage)
        assert isinstance(result[3], AIMessage)


class TestMessagesToLcMessages:
    """Tests for messages_to_lc_messages function."""

    def test_converts_user_message(self):
        """Test converting user Message to HumanMessage."""
        messages = [Message(text="Hello", sender="User")]

        result = messages_to_lc_messages(messages)

        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "Hello"

    def test_converts_ai_message(self):
        """Test converting AI Message to AIMessage."""
        messages = [Message(text="Hi there!", sender="Machine")]

        result = messages_to_lc_messages(messages)

        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "Hi there!"

    def test_converts_string_to_human_message(self):
        """Test that strings are converted to HumanMessage."""
        messages = ["Hello, how are you?"]

        result = messages_to_lc_messages(messages)

        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "Hello, how are you?"

    def test_converts_tool_result_message(self):
        """Test converting tool result Message to ToolMessage."""
        msg = Message(text="42", sender="Tool")
        msg.data = {"is_tool_result": True, "tool_call_id": "call_123"}
        messages = [msg]

        result = messages_to_lc_messages(messages)

        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert result[0].content == "42"
        assert result[0].tool_call_id == "call_123"


class TestConvertToLcMessages:
    """Tests for convert_to_lc_messages function (main entry point)."""

    def test_handles_dataframe(self):
        """Test that DataFrame input is handled correctly."""
        df = DataFrame([{"text": "Hello", "sender": "User"}])

        result = convert_to_lc_messages(df)

        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)

    def test_handles_message_list(self):
        """Test that list of Messages is handled correctly."""
        messages = [Message(text="Hello", sender="User")]

        result = convert_to_lc_messages(messages)

        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
