"""Unit tests for LangflowType input/output handlers and DataFrame output handler.

Tests serialization (output) and deserialization (input) of Langflow
Message, Data, and DataFrame types, including round-trip tests.
"""

import json

import pandas as pd
import pytest
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

from langflow_stepflow.worker.handlers import (
    DataFrameOutputHandler,
    LangflowTypeInputHandler,
    LangflowTypeOutputHandler,
)

# ---------------------------------------------------------------------------
# LangflowTypeOutputHandler — matches()
# ---------------------------------------------------------------------------


class TestLangflowTypeOutputHandlerMatches:
    def setup_method(self):
        self.handler = LangflowTypeOutputHandler()

    def test_matches_message(self):
        assert self.handler.matches(value=Message(text="hi")) is True

    def test_matches_data(self):
        assert self.handler.matches(value=Data(text="row")) is True

    def test_does_not_match_dataframe(self):
        df = DataFrame(data=[{"text": "a"}])
        assert self.handler.matches(value=df) is False

    def test_does_not_match_dict(self):
        assert self.handler.matches(value={"text": "hi"}) is False

    def test_does_not_match_string(self):
        assert self.handler.matches(value="hello") is False

    def test_does_not_match_none(self):
        assert self.handler.matches(value=None) is False

    def test_does_not_match_int(self):
        assert self.handler.matches(value=42) is False


# ---------------------------------------------------------------------------
# LangflowTypeOutputHandler — process()
# ---------------------------------------------------------------------------


class TestLangflowTypeOutputHandlerProcess:
    def setup_method(self):
        self.handler = LangflowTypeOutputHandler()

    @pytest.mark.asyncio
    async def test_serialize_message(self):
        msg = Message(text="hello world")
        result = await self.handler.process(msg)

        assert result["__langflow_type__"] == "Message"
        assert result["text"] == "hello world"
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_serialize_message_preserves_fields(self):
        msg = Message(text="test", sender="user", sender_name="Alice")
        result = await self.handler.process(msg)

        assert result["text"] == "test"
        assert result["sender"] == "user"
        assert result["sender_name"] == "Alice"
        assert result["__langflow_type__"] == "Message"

    @pytest.mark.asyncio
    async def test_serialize_data(self):
        data = Data(text="some data")
        result = await self.handler.process(data)

        assert result["__langflow_type__"] == "Data"
        assert result["text"] == "some data"
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_serialize_data_with_extra_fields(self):
        data = Data(data={"key": "value", "count": 42})
        result = await self.handler.process(data)

        assert result["__langflow_type__"] == "Data"
        # Data.model_dump() flattens the data dict into top-level keys
        assert result["key"] == "value"
        assert result["count"] == 42

    @pytest.mark.asyncio
    async def test_serialize_message_empty_text(self):
        msg = Message(text="")
        result = await self.handler.process(msg)

        assert result["__langflow_type__"] == "Message"
        assert result["text"] == ""

    @pytest.mark.asyncio
    async def test_serialize_data_unicode(self):
        data = Data(text="Unicode: \u00e9\u00e0\u00fc \u4e16\u754c \ud83c\udf0d")
        result = await self.handler.process(data)

        assert result["text"] == "Unicode: \u00e9\u00e0\u00fc \u4e16\u754c \ud83c\udf0d"


# ---------------------------------------------------------------------------
# DataFrameOutputHandler — matches()
# ---------------------------------------------------------------------------


class TestDataFrameOutputHandlerMatches:
    def setup_method(self):
        self.handler = DataFrameOutputHandler()

    def test_matches_lfx_dataframe(self):
        df = DataFrame(data=[{"text": "row1"}])
        assert self.handler.matches(value=df) is True

    def test_matches_plain_pandas_dataframe(self):
        """Plain pandas DataFrames should also match (issue #673)."""
        pdf = pd.DataFrame([{"text": "row1"}])
        assert self.handler.matches(value=pdf) is True

    def test_does_not_match_message(self):
        assert self.handler.matches(value=Message(text="hi")) is False

    def test_does_not_match_data(self):
        assert self.handler.matches(value=Data(text="hi")) is False

    def test_does_not_match_dict(self):
        assert self.handler.matches(value={"data": []}) is False

    def test_does_not_match_list(self):
        assert self.handler.matches(value=[1, 2, 3]) is False


# ---------------------------------------------------------------------------
# DataFrameOutputHandler — process()
# ---------------------------------------------------------------------------


class TestDataFrameOutputHandlerProcess:
    def setup_method(self):
        self.handler = DataFrameOutputHandler()

    @pytest.mark.asyncio
    async def test_serialize_dataframe(self):
        df = DataFrame(data=[{"text": "row1", "value": 1}])
        result = await self.handler.process(df)

        assert result["__langflow_type__"] == "DataFrame"
        assert "json_data" in result
        assert result["text_key"] == "text"
        assert result["default_value"] == ""

        # Verify json_data is valid split-format JSON
        parsed = json.loads(result["json_data"])
        assert "columns" in parsed
        assert "data" in parsed

    @pytest.mark.asyncio
    async def test_serialize_dataframe_multiple_rows(self):
        data = [
            {"text": "row1", "count": 10},
            {"text": "row2", "count": 20},
            {"text": "row3", "count": 30},
        ]
        df = DataFrame(data=data)
        result = await self.handler.process(df)

        parsed = json.loads(result["json_data"])
        assert len(parsed["data"]) == 3

    @pytest.mark.asyncio
    async def test_serialize_dataframe_preserves_text_key(self):
        df = DataFrame(data=[{"content": "test"}], text_key="content")
        result = await self.handler.process(df)

        assert result["text_key"] == "content"

    @pytest.mark.asyncio
    async def test_serialize_dataframe_single_row(self):
        df = DataFrame(data=[{"text": "only row"}])
        result = await self.handler.process(df)

        parsed = json.loads(result["json_data"])
        assert len(parsed["data"]) == 1

    @pytest.mark.asyncio
    async def test_serialize_plain_pandas_dataframe(self):
        """Plain pandas DataFrames should serialize correctly (issue #673)."""
        pdf = pd.DataFrame([{"text": "row1", "url": "http://example.com"}])
        result = await self.handler.process(pdf)

        assert result["__langflow_type__"] == "DataFrame"
        assert "json_data" in result
        # Plain pandas DataFrames don't have text_key/default_value attrs
        assert result["text_key"] == "text"
        assert result["default_value"] == ""

        parsed = json.loads(result["json_data"])
        assert "columns" in parsed
        assert len(parsed["data"]) == 1


# ---------------------------------------------------------------------------
# LangflowTypeInputHandler — matches()
# ---------------------------------------------------------------------------


class TestLangflowTypeInputHandlerMatches:
    def setup_method(self):
        self.handler = LangflowTypeInputHandler()

    def test_matches_dict_with_marker(self):
        value = {"__langflow_type__": "Message", "text": "hi"}
        assert self.handler.matches(template_field={}, value=value) is True

    def test_matches_list_with_marked_items(self):
        value = [
            {"__langflow_type__": "Data", "text": "row1"},
            {"__langflow_type__": "Data", "text": "row2"},
        ]
        assert self.handler.matches(template_field={}, value=value) is True

    def test_matches_mixed_list(self):
        """List with some marked items should still match."""
        value = [
            {"__langflow_type__": "Data", "text": "row1"},
            "plain string",
        ]
        assert self.handler.matches(template_field={}, value=value) is True

    def test_no_match_plain_dict(self):
        assert self.handler.matches(template_field={}, value={"text": "hi"}) is False

    def test_no_match_empty_list(self):
        assert self.handler.matches(template_field={}, value=[]) is False

    def test_no_match_string(self):
        assert self.handler.matches(template_field={}, value="hello") is False

    def test_no_match_none(self):
        assert self.handler.matches(template_field={}, value=None) is False

    def test_no_match_list_without_markers(self):
        value = [{"text": "row1"}, {"text": "row2"}]
        assert self.handler.matches(template_field={}, value=value) is False


# ---------------------------------------------------------------------------
# LangflowTypeInputHandler — prepare() (Message)
# ---------------------------------------------------------------------------


class TestLangflowTypeInputHandlerMessage:
    def setup_method(self):
        self.handler = LangflowTypeInputHandler()

    @pytest.mark.asyncio
    async def test_deserialize_message(self):
        serialized = {"__langflow_type__": "Message", "text": "hello"}
        fields = {"msg": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        assert isinstance(result["msg"], Message)
        assert result["msg"].text == "hello"

    @pytest.mark.asyncio
    async def test_deserialize_message_with_sender(self):
        serialized = {
            "__langflow_type__": "Message",
            "text": "test",
            "sender": "user",
            "sender_name": "Alice",
        }
        fields = {"msg": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        msg = result["msg"]
        assert isinstance(msg, Message)
        assert msg.text == "test"
        assert msg.sender == "user"
        assert msg.sender_name == "Alice"

    @pytest.mark.asyncio
    async def test_deserialize_message_empty_text(self):
        serialized = {"__langflow_type__": "Message", "text": ""}
        fields = {"msg": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        assert isinstance(result["msg"], Message)
        assert result["msg"].text == ""


# ---------------------------------------------------------------------------
# LangflowTypeInputHandler — prepare() (Data)
# ---------------------------------------------------------------------------


class TestLangflowTypeInputHandlerData:
    def setup_method(self):
        self.handler = LangflowTypeInputHandler()

    @pytest.mark.asyncio
    async def test_deserialize_data(self):
        serialized = {"__langflow_type__": "Data", "text": "some data"}
        fields = {"data_field": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        assert isinstance(result["data_field"], Data)
        assert result["data_field"].text == "some data"

    @pytest.mark.asyncio
    async def test_deserialize_data_with_extra_fields(self):
        serialized = {
            "__langflow_type__": "Data",
            "data": {"key": "value", "count": 42},
        }
        fields = {"data_field": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        data = result["data_field"]
        assert isinstance(data, Data)
        assert data.data["key"] == "value"


# ---------------------------------------------------------------------------
# LangflowTypeInputHandler — prepare() (DataFrame)
# ---------------------------------------------------------------------------


class TestLangflowTypeInputHandlerDataFrame:
    def setup_method(self):
        self.handler = LangflowTypeInputHandler()

    @pytest.mark.asyncio
    async def test_deserialize_dataframe(self):
        # Build the split-JSON format that DataFrameOutputHandler produces
        import pandas as pd

        pd_df = pd.DataFrame([{"text": "row1", "count": 1}])
        json_str = pd_df.to_json(orient="split")

        serialized = {
            "__langflow_type__": "DataFrame",
            "json_data": json_str,
            "text_key": "text",
            "default_value": "",
        }
        fields = {"df_field": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        df = result["df_field"]
        assert df.__class__.__name__ == "DataFrame"

    @pytest.mark.asyncio
    async def test_deserialize_dataframe_with_none_values(self):
        """DataFrames with NaN/None values should be handled."""
        import pandas as pd

        pd_df = pd.DataFrame([{"text": "row1", "value": None}])
        json_str = pd_df.to_json(orient="split")

        serialized = {
            "__langflow_type__": "DataFrame",
            "json_data": json_str,
            "text_key": "text",
            "default_value": "",
        }
        fields = {"df_field": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        assert result["df_field"].__class__.__name__ == "DataFrame"

    @pytest.mark.asyncio
    async def test_deserialize_dataframe_missing_json_data_falls_back(self):
        """Missing json_data should trigger recovery fallback."""
        serialized = {
            "__langflow_type__": "DataFrame",
            "text_key": "text",
            "default_value": "",
        }
        fields = {"df_field": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        # Recovery also fails (no json_data at all) — returns raw dict
        assert isinstance(result["df_field"], dict)


# ---------------------------------------------------------------------------
# LangflowTypeInputHandler — prepare() (list handling)
# ---------------------------------------------------------------------------


class TestLangflowTypeInputHandlerLists:
    def setup_method(self):
        self.handler = LangflowTypeInputHandler()

    @pytest.mark.asyncio
    async def test_deserialize_list_of_messages(self):
        value = [
            {"__langflow_type__": "Message", "text": "msg1"},
            {"__langflow_type__": "Message", "text": "msg2"},
        ]
        fields = {"msgs": (value, {})}
        result = await self.handler.prepare(fields, None)

        assert len(result["msgs"]) == 2
        assert isinstance(result["msgs"][0], Message)
        assert isinstance(result["msgs"][1], Message)
        assert result["msgs"][0].text == "msg1"
        assert result["msgs"][1].text == "msg2"

    @pytest.mark.asyncio
    async def test_deserialize_list_of_data(self):
        value = [
            {"__langflow_type__": "Data", "text": "d1"},
            {"__langflow_type__": "Data", "text": "d2"},
        ]
        fields = {"items": (value, {})}
        result = await self.handler.prepare(fields, None)

        assert len(result["items"]) == 2
        assert all(isinstance(item, Data) for item in result["items"])

    @pytest.mark.asyncio
    async def test_mixed_list_preserves_unmarked_items(self):
        """Non-marked items in a list should pass through unchanged."""
        value = [
            {"__langflow_type__": "Message", "text": "msg1"},
            "plain string",
            42,
            None,
        ]
        fields = {"items": (value, {})}
        result = await self.handler.prepare(fields, None)

        items = result["items"]
        assert len(items) == 4
        assert isinstance(items[0], Message)
        assert items[1] == "plain string"
        assert items[2] == 42
        assert items[3] is None

    @pytest.mark.asyncio
    async def test_deserialize_multiple_fields(self):
        """Multiple fields should all be processed."""
        fields = {
            "msg": ({"__langflow_type__": "Message", "text": "hello"}, {}),
            "data": ({"__langflow_type__": "Data", "text": "world"}, {}),
        }
        result = await self.handler.prepare(fields, None)

        assert isinstance(result["msg"], Message)
        assert isinstance(result["data"], Data)


# ---------------------------------------------------------------------------
# LangflowTypeInputHandler — unknown / edge cases
# ---------------------------------------------------------------------------


class TestLangflowTypeInputHandlerEdgeCases:
    def setup_method(self):
        self.handler = LangflowTypeInputHandler()

    @pytest.mark.asyncio
    async def test_unknown_langflow_type_returns_dict(self):
        """Unknown __langflow_type__ values should return the raw dict."""
        serialized = {"__langflow_type__": "UnknownType", "data": "test"}
        fields = {"field": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        assert isinstance(result["field"], dict)
        assert result["field"]["__langflow_type__"] == "UnknownType"

    @pytest.mark.asyncio
    async def test_empty_langflow_type_returns_dict(self):
        """Empty __langflow_type__ value should return the raw dict."""
        serialized = {"__langflow_type__": "", "text": "test"}
        fields = {"field": (serialized, {})}
        result = await self.handler.prepare(fields, None)

        assert isinstance(result["field"], dict)


# ---------------------------------------------------------------------------
# Round-trip tests: serialize → deserialize
# ---------------------------------------------------------------------------


class TestLangflowTypeRoundTrip:
    def setup_method(self):
        self.output_handler = LangflowTypeOutputHandler()
        self.input_handler = LangflowTypeInputHandler()

    @pytest.mark.asyncio
    async def test_message_round_trip(self):
        original = Message(text="hello world")
        serialized = await self.output_handler.process(original)

        fields = {"msg": (serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        restored = result["msg"]
        assert isinstance(restored, Message)
        assert restored.text == original.text

    @pytest.mark.asyncio
    async def test_message_with_metadata_round_trip(self):
        original = Message(text="test", sender="user", sender_name="Bob")
        serialized = await self.output_handler.process(original)

        fields = {"msg": (serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        restored = result["msg"]
        assert isinstance(restored, Message)
        assert restored.text == "test"
        assert restored.sender == "user"
        assert restored.sender_name == "Bob"

    @pytest.mark.asyncio
    async def test_data_round_trip(self):
        original = Data(text="some data", data={"key": "value"})
        serialized = await self.output_handler.process(original)

        fields = {"data": (serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        restored = result["data"]
        assert isinstance(restored, Data)
        assert restored.text == original.text

    @pytest.mark.asyncio
    async def test_list_of_messages_round_trip(self):
        originals = [Message(text="msg1"), Message(text="msg2")]

        serialized_list = [await self.output_handler.process(msg) for msg in originals]

        fields = {"msgs": (serialized_list, {})}
        result = await self.input_handler.prepare(fields, None)

        restored = result["msgs"]
        assert len(restored) == 2
        assert all(isinstance(m, Message) for m in restored)
        assert restored[0].text == "msg1"
        assert restored[1].text == "msg2"


class TestDataFrameRoundTrip:
    """Round-trip tests for DataFrame: serialize with DataFrameOutputHandler,
    deserialize with LangflowTypeInputHandler."""

    def setup_method(self):
        self.output_handler = DataFrameOutputHandler()
        self.input_handler = LangflowTypeInputHandler()

    @pytest.mark.asyncio
    async def test_dataframe_round_trip(self):
        original = DataFrame(
            data=[
                {"text": "row1", "count": 10},
                {"text": "row2", "count": 20},
            ]
        )

        serialized = await self.output_handler.process(original)
        assert serialized["__langflow_type__"] == "DataFrame"

        fields = {"df": (serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        restored = result["df"]
        assert restored.__class__.__name__ == "DataFrame"

    @pytest.mark.asyncio
    async def test_dataframe_round_trip_preserves_text_key(self):
        original = DataFrame(
            data=[{"content": "test"}],
            text_key="content",
        )

        serialized = await self.output_handler.process(original)
        assert serialized["text_key"] == "content"

        fields = {"df": (serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        restored = result["df"]
        assert restored.__class__.__name__ == "DataFrame"


class TestPandasDataFrameRoundTrip:
    """Round-trip tests for plain pandas DataFrames (issue #673).

    Components compiled from flow JSON blobs may produce plain pandas
    DataFrames instead of lfx DataFrames, depending on the Langflow
    version that exported the flow.
    """

    def setup_method(self):
        self.output_handler = DataFrameOutputHandler()
        self.input_handler = LangflowTypeInputHandler()

    @pytest.mark.asyncio
    async def test_pandas_dataframe_round_trip(self):
        original = pd.DataFrame(
            [
                {"text": "row1", "count": 10},
                {"text": "row2", "count": 20},
            ]
        )

        serialized = await self.output_handler.process(original)
        assert serialized["__langflow_type__"] == "DataFrame"

        fields = {"df": (serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        restored = result["df"]
        assert restored.__class__.__name__ == "DataFrame"
