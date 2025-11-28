from lfx.schema.json_schema import create_input_schema_from_json_schema


def test_type_as_list():
    # Schema with type as a list (JSON Schema feature)
    schema = {"type": "object", "properties": {"field": {"type": ["string", "integer"]}}}
    # This should now succeed
    model = create_input_schema_from_json_schema(schema)
    assert model


def test_type_as_list_with_null():
    # Schema with type as a list including null
    schema = {"type": "object", "properties": {"field": {"type": ["string", "null"]}}}
    model = create_input_schema_from_json_schema(schema)
    assert model
