"""Unit tests for LFX CLI result extraction utilities."""

from unittest.mock import MagicMock

from lfx.cli.result_extraction import (
    _extract_value,
    _get_result_type,
    _value_to_json_string,
    _value_to_text_string,
    extract_message_from_result,
    extract_structured_result,
    extract_text_from_result,
)


class TestValueToJsonString:
    """Tests for _value_to_json_string function."""

    def test_none_returns_null(self):
        """Test that None returns 'null'."""
        assert _value_to_json_string(None) == "null"

    def test_string_value(self):
        """Test JSON serialization of string."""
        result = _value_to_json_string("hello")
        assert result == '"hello"'

    def test_dict_value(self):
        """Test JSON serialization of dict."""
        result = _value_to_json_string({"key": "value"})
        assert result == '{"key": "value"}'

    def test_list_value(self):
        """Test JSON serialization of list."""
        result = _value_to_json_string([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_int_value(self):
        """Test JSON serialization of int."""
        result = _value_to_json_string(42)
        assert result == "42"

    def test_float_value(self):
        """Test JSON serialization of float."""
        result = _value_to_json_string(3.14)
        assert result == "3.14"

    def test_bool_value(self):
        """Test JSON serialization of bool."""
        assert _value_to_json_string(value=True) == "true"
        assert _value_to_json_string(value=False) == "false"

    def test_pydantic_model_with_model_dump_json(self):
        """Test JSON serialization of Pydantic model with model_dump_json."""
        mock_model = MagicMock()
        mock_model.model_dump_json.return_value = '{"field": "value"}'

        result = _value_to_json_string(mock_model)
        assert result == '{"field": "value"}'

    def test_pydantic_model_with_model_dump(self):
        """Test JSON serialization of Pydantic model with model_dump."""
        mock_model = MagicMock(spec=["model_dump"])
        mock_model.model_dump.return_value = {"field": "value"}

        result = _value_to_json_string(mock_model)
        assert result == '{"field": "value"}'

    def test_data_object_with_data_attribute(self):
        """Test JSON serialization of object with data attribute."""
        mock_data = MagicMock(spec=["data"])
        mock_data.data = {"nested": "data"}

        result = _value_to_json_string(mock_data)
        assert result == '{"nested": "data"}'

    def test_fallback_to_str(self):
        """Test fallback to string representation for unsupported types."""

        class CustomClass:
            def __str__(self):
                return "custom_string"

        result = _value_to_json_string(CustomClass())
        assert result == "custom_string"

    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        result = _value_to_json_string("Hello 世界 🌍")
        assert result == '"Hello 世界 🌍"'


class TestValueToTextString:
    """Tests for _value_to_text_string function."""

    def test_none_returns_empty_string(self):
        """Test that None returns empty string."""
        assert _value_to_text_string(None) == ""

    def test_string_value(self):
        """Test that string returns as-is."""
        assert _value_to_text_string("hello") == "hello"

    def test_object_with_text_attribute(self):
        """Test extraction from object with text attribute."""
        mock_obj = MagicMock()
        mock_obj.text = "extracted text"

        result = _value_to_text_string(mock_obj)
        assert result == "extracted text"

    def test_data_object_with_text_in_data(self):
        """Test extraction from data object with text key."""
        mock_data = MagicMock(spec=["data"])
        mock_data.data = {"text": "data text", "other": "value"}

        result = _value_to_text_string(mock_data)
        assert result == "data text"

    def test_data_object_with_string_data(self):
        """Test extraction from data object with string data."""
        mock_data = MagicMock(spec=["data"])
        mock_data.data = "string data"

        result = _value_to_text_string(mock_data)
        assert result == "string data"

    def test_data_object_with_dict_no_text(self):
        """Test extraction from data object with dict without text key."""
        mock_data = MagicMock(spec=["data"])
        mock_data.data = {"key1": "value1", "key2": "value2"}

        result = _value_to_text_string(mock_data)
        # Should convert to JSON
        assert "key1" in result
        assert "value1" in result

    def test_dict_with_text_key(self):
        """Test extraction from dict with text key."""
        result = _value_to_text_string({"text": "dict text", "other": "value"})
        assert result == "dict text"

    def test_dict_without_text_key(self):
        """Test dict without text key converts to JSON."""
        result = _value_to_text_string({"key": "value"})
        assert result == '{"key": "value"}'

    def test_list_converts_to_json(self):
        """Test list converts to JSON."""
        result = _value_to_text_string([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_pydantic_model(self):
        """Test Pydantic model conversion."""
        mock_model = MagicMock(spec=["model_dump"])
        mock_model.model_dump.return_value = {"field": "value"}

        result = _value_to_text_string(mock_model)
        assert result == '{"field": "value"}'

    def test_fallback_to_str(self):
        """Test fallback to string representation."""

        class CustomClass:
            def __str__(self):
                return "custom_string"

        result = _value_to_text_string(CustomClass())
        assert result == "custom_string"


class TestExtractValue:
    """Tests for _extract_value function."""

    def test_none_returns_none(self):
        """Test that None returns None."""
        assert _extract_value(None) is None

    def test_message_with_text_extract_true(self):
        """Test extraction from message with extract_text=True."""
        mock_msg = MagicMock()
        mock_msg.text = "message text"

        result = _extract_value(mock_msg, extract_text=True)
        assert result == "message text"

    def test_message_with_text_extract_false(self):
        """Test extraction from message with extract_text=False."""
        mock_msg = MagicMock()
        mock_msg.text = "message text"

        result = _extract_value(mock_msg, extract_text=False)
        # When extract_text is False, it should not extract text
        # but since message has text attribute, it goes to pydantic check
        assert result is not None

    def test_data_object_extract_text_true(self):
        """Test extraction from data object with extract_text=True."""
        mock_data = MagicMock(spec=["data"])
        mock_data.data = {"text": "data text", "metadata": "info"}

        result = _extract_value(mock_data, extract_text=True)
        assert result == "data text"

    def test_data_object_extract_text_false(self):
        """Test extraction from data object with extract_text=False."""
        mock_data = MagicMock(spec=["data"])
        mock_data.data = {"text": "data text", "metadata": "info"}

        result = _extract_value(mock_data, extract_text=False)
        assert result == {"text": "data text", "metadata": "info"}

    def test_data_object_no_text_key(self):
        """Test extraction from data object without text key."""
        mock_data = MagicMock(spec=["data"])
        mock_data.data = {"key": "value"}

        result = _extract_value(mock_data, extract_text=True)
        assert result == {"key": "value"}

    def test_pydantic_model_to_dict(self):
        """Test Pydantic model conversion to dict."""
        mock_model = MagicMock(spec=["model_dump"])
        mock_model.model_dump.return_value = {"field": "value"}

        result = _extract_value(mock_model)
        assert result == {"field": "value"}

    def test_dict_returns_as_is(self):
        """Test dict returns as-is."""
        data = {"key": "value"}
        result = _extract_value(data)
        assert result == {"key": "value"}

    def test_list_returns_as_is(self):
        """Test list returns as-is."""
        data = [1, 2, 3]
        result = _extract_value(data)
        assert result == [1, 2, 3]

    def test_primitives_return_as_is(self):
        """Test primitives return as-is."""
        assert _extract_value("string") == "string"
        assert _extract_value(42) == 42
        assert _extract_value(3.14) == 3.14
        assert _extract_value(value=True) is True

    def test_fallback_to_str(self):
        """Test fallback to string for unsupported types."""

        class CustomClass:
            def __str__(self):
                return "custom"

        result = _extract_value(CustomClass())
        assert result == "custom"


class TestGetResultType:
    """Tests for _get_result_type function."""

    def test_message_type(self):
        """Test detection of message type."""
        mock_msg = MagicMock()
        mock_msg.text = "text"

        result = _get_result_type(mock_msg)
        assert result == "message"

    def test_data_type(self):
        """Test detection of data type."""
        mock_data = MagicMock(spec=["data"])
        mock_data.data = {"key": "value"}

        result = _get_result_type(mock_data)
        assert result == "data"

    def test_dict_type(self):
        """Test detection of dict type."""
        result = _get_result_type({"key": "value"})
        assert result == "dict"

    def test_list_type(self):
        """Test detection of list type."""
        result = _get_result_type([1, 2, 3])
        assert result == "list"

    def test_text_type(self):
        """Test detection of text type."""
        result = _get_result_type("string")
        assert result == "text"

    def test_object_type(self):
        """Test detection of object type for other types."""

        class CustomClass:
            pass

        result = _get_result_type(CustomClass())
        assert result == "object"

    def test_int_is_object(self):
        """Test that int is classified as object (not text)."""
        result = _get_result_type(42)
        assert result == "object"


class TestExtractMessageFromResult:
    """Tests for extract_message_from_result function."""

    def test_chat_output_extraction(self):
        """Test extraction from Chat Output component."""
        from lfx.graph.schema import ResultData
        from lfx.schema.message import Message

        message = Message(text="Hello World")
        result_data = ResultData(
            results={"message": message}, component_display_name="Chat Output", component_id="test-123"
        )

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.result_dict = result_data

        result = extract_message_from_result([mock_result])
        assert "Hello" in result
        assert "World" in result

    def test_run_flow_extraction(self):
        """Test extraction from Run Flow component."""
        from lfx.graph.schema import ResultData

        result_data = ResultData(
            results={"output": {"text": "subflow result"}}, component_display_name="Run Flow", component_id="test-456"
        )

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Run Flow"
        mock_result.result_dict = result_data

        result = extract_message_from_result([mock_result])
        assert "subflow result" in result

    def test_no_response_generated(self):
        """Test when no valid component is found."""
        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Other Component"

        result = extract_message_from_result([mock_result])
        assert result == "No response generated"

    def test_empty_results(self):
        """Test with empty results list."""
        result = extract_message_from_result([])
        assert result == "No response generated"

    def test_result_without_vertex(self):
        """Test handling of result without vertex attribute."""
        mock_result = MagicMock(spec=[])  # No vertex attribute

        result = extract_message_from_result([mock_result])
        assert result == "No response generated"


class TestExtractTextFromResult:
    """Tests for extract_text_from_result function."""

    def test_chat_output_extraction(self):
        """Test text extraction from Chat Output component."""
        from lfx.graph.schema import ResultData
        from lfx.schema.message import Message

        message = Message(text="Hello World")
        result_data = ResultData(
            results={"message": message}, component_display_name="Chat Output", component_id="test-123"
        )

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.result_dict = result_data

        result = extract_text_from_result([mock_result])
        assert result == "Hello World"

    def test_run_flow_extraction(self):
        """Test text extraction from Run Flow component."""
        from lfx.graph.schema import ResultData
        from lfx.schema.message import Message

        message = Message(text="subflow text")
        result_data = ResultData(
            results={"output": message}, component_display_name="Run Flow", component_id="test-456"
        )

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Run Flow"
        mock_result.result_dict = result_data

        result = extract_text_from_result([mock_result])
        assert result == "subflow text"

    def test_no_response_generated(self):
        """Test when no valid component is found."""
        result = extract_text_from_result([])
        assert result == "No response generated"


class TestExtractStructuredResult:
    """Tests for extract_structured_result function."""

    def test_chat_output_success(self):
        """Test structured extraction from Chat Output."""
        from lfx.graph.schema import ResultData
        from lfx.schema.message import Message

        message = Message(text="Test message")
        result_data = ResultData(
            results={"message": message}, component_display_name="Chat Output", component_id="vertex-123"
        )

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.vertex.id = "vertex-123"
        mock_result.result_dict = result_data

        result = extract_structured_result([mock_result])

        assert result["success"] is True
        assert result["type"] == "message"
        assert result["component"] == "Chat Output"
        assert result["component_id"] == "vertex-123"
        assert result["result"] == "Test message"

    def test_run_flow_success(self):
        """Test structured extraction from Run Flow."""
        from lfx.graph.schema import ResultData

        result_data = ResultData(
            results={"flow_output": {"data": "structured data"}},
            component_display_name="Run Flow",
            component_id="vertex-456",
        )

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Run Flow"
        mock_result.vertex.id = "vertex-456"
        mock_result.result_dict = result_data

        result = extract_structured_result([mock_result])

        assert result["success"] is True
        assert result["component"] == "Run Flow"
        assert result["output_name"] == "flow_output"

    def test_no_results(self):
        """Test with empty results."""
        result = extract_structured_result([])

        assert result["success"] is False
        assert result["type"] == "error"
        assert result["text"] == "No response generated"

    def test_extract_text_false(self):
        """Test with extract_text=False."""
        from lfx.graph.schema import ResultData
        from lfx.schema.message import Message

        message = Message(text="Test message")
        result_data = ResultData(
            results={"message": message}, component_display_name="Chat Output", component_id="vertex-123"
        )

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.vertex.id = "vertex-123"
        mock_result.result_dict = result_data

        result = extract_structured_result([mock_result], extract_text=False)

        assert result["success"] is True
        # When extract_text=False, the message is converted to dict via model_dump()
        # since Message has text attribute and extract_text=False, it goes to pydantic model handling
        assert isinstance(result["result"], dict)
        assert result["result"]["text"] == "Test message"

    def test_run_flow_skips_component_as_tool(self):
        """Test that Run Flow skips component_as_tool output."""
        from lfx.graph.schema import ResultData

        result_data = ResultData(
            results={
                "component_as_tool": {"tool": "data"},
                "actual_output": {"value": "real result"},
            },
            component_display_name="Run Flow",
            component_id="vertex-789",
        )

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Run Flow"
        mock_result.vertex.id = "vertex-789"
        mock_result.result_dict = result_data

        result = extract_structured_result([mock_result])

        assert result["success"] is True
        assert result["output_name"] == "actual_output"
        assert "component_as_tool" not in str(result.get("output_name", ""))
