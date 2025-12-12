from typing import Any

from lfx.base.mcp.util import _fill_defaults, _post_process_arguments
from lfx.schema.json_schema import create_input_schema_from_json_schema
from pydantic import BaseModel


class MockSchema(BaseModel):
    # Required fields - should NOT be filled
    req_name: str
    req_age: int

    # Optional fields - SHOULD be filled by _fill_defaults
    opt_name: str | None = None
    opt_tags: list[str] | None = None
    opt_meta: dict[str, Any] | None = None
    opt_active: bool | None = None


def test_fill_defaults():
    provided_args = {}
    _fill_defaults(MockSchema, provided_args)

    # Required fields should NOT be filled (let Pydantic raise validation error)
    assert "req_name" not in provided_args
    assert "req_age" not in provided_args

    # Optional fields SHOULD be filled with type-based defaults
    assert provided_args["opt_name"] == ""
    assert provided_args["opt_tags"] == []
    assert provided_args["opt_meta"] == {}
    assert provided_args["opt_active"] is False


def test_post_process_arguments_json_parsing():
    class JsonSchema(BaseModel):
        data: list[dict[str, Any]]
        config: dict[str, Any]

    arguments = {"data": '[{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]', "config": '{"timeout": 10}'}
    _post_process_arguments(JsonSchema, arguments)

    assert isinstance(arguments["data"], list)
    assert len(arguments["data"]) == 2
    # Check the transformation logic (it wraps values in {"value": ...})
    # transformed_record[k] = {"value": v}
    # Note: The logic in _post_process_arguments converts ints to strings for values
    assert arguments["data"][0]["id"] == {"value": "1"}
    assert arguments["data"][0]["val"] == {"value": "a"}

    assert isinstance(arguments["config"], dict)
    assert arguments["config"]["timeout"] == 10


def test_create_input_schema_complex():
    # Test a field with complex schema (> 5 properties)
    schema = {
        "type": "object",
        "properties": {
            "complex_field": {
                "type": "object",
                "properties": {
                    "a": {"type": "string"},
                    "b": {"type": "string"},
                    "c": {"type": "string"},
                    "d": {"type": "string"},
                    "e": {"type": "string"},
                    "f": {"type": "string"},  # > 5 properties
                },
            }
        },
    }

    model = create_input_schema_from_json_schema(schema)
    # complex_field should be str because it has > 5 properties
    field_info = model.model_fields["complex_field"]
    # Pydantic v2 might wrap it in Optional if not required
    # But create_input_schema_from_json_schema handles required/optional
    # Here it is not required, so it should be Optional[str] or str | None

    # Check if str is in the type annotation
    annotation = field_info.annotation
    # It might be Union[str, NoneType]
    assert str in getattr(annotation, "__args__", [annotation])


def test_create_input_schema_complex_array():
    # Test an array with complex items
    schema = {
        "type": "object",
        "properties": {
            "complex_array": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "string"},
                        "b": {"type": "string"},
                        "c": {"type": "string"},
                        "d": {"type": "string"},
                        "e": {"type": "string"},
                        "f": {"type": "string"},  # > 5 properties
                    },
                },
            }
        },
    }

    model = create_input_schema_from_json_schema(schema)
    field_info = model.model_fields["complex_array"]
    # Should be str (JSON input) because items are complex
    annotation = field_info.annotation
    assert str in getattr(annotation, "__args__", [annotation])
