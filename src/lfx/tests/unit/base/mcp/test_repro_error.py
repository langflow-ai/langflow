from lfx.schema.json_schema import create_input_schema_from_json_schema


def test_anyof_with_list_type():
    # Schema with anyOf containing array type
    schema = {
        "type": "object",
        "properties": {"field": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}},
    }
    # This should create Union[str, List[str]]
    model = create_input_schema_from_json_schema(schema)
    assert model


def test_anyof_with_complex_types():
    # Schema with anyOf containing object and array
    schema = {
        "type": "object",
        "properties": {
            "field": {
                "anyOf": [
                    {"type": "object", "properties": {"a": {"type": "string"}}},
                    {"type": "array", "items": {"type": "integer"}},
                ]
            }
        },
    }
    model = create_input_schema_from_json_schema(schema)
    assert model


def test_anyof_with_nested_anyof():
    # Nested anyOf
    schema = {
        "type": "object",
        "properties": {
            "field": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"anyOf": [{"type": "integer"}, {"type": "boolean"}]}},
                ]
            }
        },
    }
    model = create_input_schema_from_json_schema(schema)
    assert model


def test_anyof_with_unhashable_defaults():
    # Schema with default values that are lists (should not affect type creation but checking)
    schema = {
        "type": "object",
        "properties": {"field": {"type": "array", "items": {"type": "string"}, "default": ["a", "b"]}},
    }
    model = create_input_schema_from_json_schema(schema)
    assert model
