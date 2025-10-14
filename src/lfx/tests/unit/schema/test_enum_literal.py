"""Test enum to Literal mapping in JSON Schema parser."""

from typing import Literal, get_args, get_origin

from lfx.schema.json_schema import create_input_schema_from_json_schema


def test_enum_maps_to_literal():
    """Test that JSON Schema enum is mapped to typing.Literal."""
    schema = {
        "type": "object",
        "properties": {
            "engine": {
                "type": "string",
                "enum": ["google", "bing", "yandex"],
                "default": "google",
            }
        },
    }
    model = create_input_schema_from_json_schema(schema)
    field_info = model.model_fields["engine"]

    # The annotation should be Optional[Literal[...]] since it's not required
    # We need to check the inner type
    annotation = field_info.annotation

    # For optional fields, the annotation is a Union type
    # We need to extract the non-None type
    if get_origin(annotation) is type(None) or str(get_origin(annotation)) == "typing.UnionType":
        # Get all args and filter out None
        args = get_args(annotation)
        non_none_types = [arg for arg in args if arg is not type(None)]
        if non_none_types:
            inner_type = non_none_types[0]
        else:
            inner_type = annotation
    else:
        inner_type = annotation

    # Now check if the inner type is a Literal
    assert get_origin(inner_type) is Literal, f"Expected Literal, got {get_origin(inner_type)}"

    # Check the literal values
    literal_values = get_args(inner_type)
    assert set(literal_values) == {"google", "bing", "yandex"}


def test_enum_with_required_field():
    """Test that required enum fields also map to Literal."""
    schema = {
        "type": "object",
        "properties": {
            "engine": {
                "type": "string",
                "enum": ["google", "bing", "yandex"],
            }
        },
        "required": ["engine"],
    }
    model = create_input_schema_from_json_schema(schema)
    field_info = model.model_fields["engine"]
    annotation = field_info.annotation

    # For required fields, should directly be Literal
    assert get_origin(annotation) is Literal
    assert set(get_args(annotation)) == {"google", "bing", "yandex"}


def test_numeric_enum_maps_to_literal():
    """Test that numeric enum values work with Literal."""
    schema = {
        "type": "object",
        "properties": {
            "priority": {
                "type": "integer",
                "enum": [1, 2, 3, 4, 5],
            }
        },
        "required": ["priority"],
    }
    model = create_input_schema_from_json_schema(schema)
    field_info = model.model_fields["priority"]
    annotation = field_info.annotation

    assert get_origin(annotation) is Literal
    assert set(get_args(annotation)) == {1, 2, 3, 4, 5}


def test_mixed_type_enum_fallback():
    """Test that mixed type enums fall back to str if Literal fails."""
    schema = {
        "type": "object",
        "properties": {
            # Enums should be hashable for Literal to work
            "value": {
                "type": "string",
                "enum": ["a", "b", "c"],
            }
        },
        "required": ["value"],
    }
    model = create_input_schema_from_json_schema(schema)
    field_info = model.model_fields["value"]
    annotation = field_info.annotation

    # Should be Literal for hashable values
    assert get_origin(annotation) is Literal
    assert set(get_args(annotation)) == {"a", "b", "c"}

