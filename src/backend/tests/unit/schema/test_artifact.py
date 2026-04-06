"""Tests for langflow.schema.artifact module."""

from enum import Enum

from langflow.schema.artifact import ArtifactType, _to_list_of_dicts, get_artifact_type, post_process_raw
from langflow.schema.data import Data
from pydantic import BaseModel


class TestArtifactType:
    """Tests for the ArtifactType enum."""

    def test_enum_values(self):
        assert ArtifactType.TEXT.value == "text"
        assert ArtifactType.DATA.value == "data"
        assert ArtifactType.OBJECT.value == "object"
        assert ArtifactType.ARRAY.value == "array"
        assert ArtifactType.STREAM.value == "stream"
        assert ArtifactType.UNKNOWN.value == "unknown"
        assert ArtifactType.MESSAGE.value == "message"

    def test_is_string_enum(self):
        assert issubclass(ArtifactType, str)
        assert issubclass(ArtifactType, Enum)


class TestGetArtifactType:
    """Tests for get_artifact_type function."""

    def test_string_returns_text(self):
        assert get_artifact_type("hello") == "text"

    def test_empty_string_returns_text(self):
        assert get_artifact_type("") == "text"

    def test_dict_returns_object(self):
        assert get_artifact_type({"key": "value"}) == "object"

    def test_empty_dict_returns_object(self):
        assert get_artifact_type({}) == "object"

    def test_list_returns_array(self):
        assert get_artifact_type([1, 2, 3]) == "array"

    def test_empty_list_returns_array(self):
        assert get_artifact_type([]) == "array"

    def test_none_returns_unknown(self):
        assert get_artifact_type(None) == "unknown"

    def test_int_returns_unknown(self):
        assert get_artifact_type(42) == "unknown"

    def test_generator_build_result_returns_stream(self):
        gen = (x for x in range(3))
        assert get_artifact_type(None, build_result=gen) == "stream"

    def test_message_with_string_text(self):
        from langflow.schema.message import Message

        m = Message(text="hello")
        assert get_artifact_type(m) == "message"

    def test_message_with_generator_text(self):
        from langflow.schema.message import Message

        gen = (x for x in range(3))
        m = Message(text=gen)
        assert get_artifact_type(m) == "stream"

    def test_data_with_dict(self):
        d = Data(data={"key": "value"})
        assert get_artifact_type(d) == "object"

    def test_data_with_string(self):
        d = Data(data={"text_key": "hello"})
        result = get_artifact_type(d)
        assert result == "object"


class _SimpleModel(BaseModel):
    key: str = "value"


class TestToListOfDicts:
    """Tests for _to_list_of_dicts function."""

    def test_items_with_model_dump(self):
        item = _SimpleModel(key="value")
        result = _to_list_of_dicts([item])
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["key"] == "value"

    def test_items_without_model_dump(self):
        result = _to_list_of_dicts([1, 2, "hello"])
        assert result == ["1", "2", "hello"]

    def test_empty_list(self):
        result = _to_list_of_dicts([])
        assert result == []

    def test_mixed_items(self):
        item_with_dump = _SimpleModel(key="test")
        result = _to_list_of_dicts([item_with_dump, 42])
        assert len(result) == 2
        assert isinstance(result[0], dict)
        assert result[0]["key"] == "test"
        assert result[1] == "42"


class TestPostProcessRaw:
    """Tests for post_process_raw function."""

    def test_stream_type_returns_empty_string(self):
        raw, artifact_type = post_process_raw("anything", "stream")
        assert raw == ""
        assert artifact_type == "stream"

    def test_unknown_with_none_returns_none(self):
        raw, artifact_type = post_process_raw(None, "unknown")
        assert raw is None
        assert artifact_type == "unknown"

    def test_unknown_with_dict(self):
        raw, artifact_type = post_process_raw({"key": "value"}, "unknown")
        assert artifact_type == "object"
        assert isinstance(raw, dict)

    def test_unknown_with_non_serializable(self):
        raw, artifact_type = post_process_raw(42, "unknown")
        assert raw == "Built Successfully ✨"
        assert artifact_type == "unknown"

    def test_text_type_passes_through(self):
        raw, artifact_type = post_process_raw("hello", "text")
        assert raw == "hello"
        assert artifact_type == "text"

    def test_object_type_passes_through(self):
        d = {"key": "value"}
        raw, artifact_type = post_process_raw(d, "object")
        assert raw == d
        assert artifact_type == "object"

    def test_array_with_list(self):
        items = [1, 2, 3]
        raw, artifact_type = post_process_raw(items, "array")
        assert isinstance(raw, list)
        assert artifact_type == "array"
