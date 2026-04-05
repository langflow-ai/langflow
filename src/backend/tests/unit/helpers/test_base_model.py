"""Tests for langflow.helpers.base_model module."""

import pytest
from pydantic import BaseModel as PydanticBaseModel

from langflow.helpers.base_model import (
    _get_type_annotation,
    build_model_from_schema,
    coalesce_bool,
)


class TestGetTypeAnnotation:
    def test_str(self):
        assert _get_type_annotation("str", multiple=False) is str

    def test_int(self):
        assert _get_type_annotation("int", multiple=False) is int

    def test_float(self):
        assert _get_type_annotation("float", multiple=False) is float

    def test_bool(self):
        assert _get_type_annotation("bool", multiple=False) is bool

    def test_boolean(self):
        assert _get_type_annotation("boolean", multiple=False) is bool

    def test_number(self):
        assert _get_type_annotation("number", multiple=False) is float

    def test_text(self):
        assert _get_type_annotation("text", multiple=False) is str

    def test_multiple_str(self):
        result = _get_type_annotation("str", multiple=True)
        assert result == list[str]

    def test_multiple_int(self):
        result = _get_type_annotation("int", multiple=True)
        assert result == list[int]

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid type"):
            _get_type_annotation("unknown_type", multiple=False)


class TestBuildModelFromSchema:
    def test_basic_schema(self):
        schema = [
            {"name": "name", "type": "str", "description": "The name", "multiple": False},
            {"name": "age", "type": "int", "description": "The age", "multiple": False},
        ]
        Model = build_model_from_schema(schema)
        assert issubclass(Model, PydanticBaseModel)
        instance = Model(name="Alice", age=25)
        assert instance.name == "Alice"
        assert instance.age == 25

    def test_multiple_field(self):
        schema = [
            {"name": "tags", "type": "str", "description": "Tags", "multiple": True},
        ]
        Model = build_model_from_schema(schema)
        instance = Model(tags=["a", "b"])
        assert instance.tags == ["a", "b"]

    def test_empty_schema(self):
        Model = build_model_from_schema([])
        instance = Model()
        assert isinstance(instance, PydanticBaseModel)

    def test_bool_field(self):
        schema = [
            {"name": "active", "type": "bool", "description": "Is active", "multiple": False},
        ]
        Model = build_model_from_schema(schema)
        instance = Model(active=True)
        assert instance.active is True

    def test_multiple_coalesced_from_string(self):
        schema = [
            {"name": "items", "type": "str", "description": "Items", "multiple": "true"},
        ]
        Model = build_model_from_schema(schema)
        instance = Model(items=["x"])
        assert instance.items == ["x"]


class TestCoalesceBool:
    def test_true_bool(self):
        assert coalesce_bool(True) is True

    def test_false_bool(self):
        assert coalesce_bool(False) is False

    def test_string_true(self):
        assert coalesce_bool("true") is True

    def test_string_True(self):
        assert coalesce_bool("True") is True

    def test_string_yes(self):
        assert coalesce_bool("yes") is True

    def test_string_1(self):
        assert coalesce_bool("1") is True

    def test_string_t(self):
        assert coalesce_bool("t") is True

    def test_string_y(self):
        assert coalesce_bool("y") is True

    def test_string_false(self):
        assert coalesce_bool("false") is False

    def test_string_no(self):
        assert coalesce_bool("no") is False

    def test_int_1(self):
        assert coalesce_bool(1) is True

    def test_int_0(self):
        assert coalesce_bool(0) is False

    def test_none(self):
        assert coalesce_bool(None) is False

    def test_list(self):
        assert coalesce_bool([]) is False

    def test_dict(self):
        assert coalesce_bool({}) is False
