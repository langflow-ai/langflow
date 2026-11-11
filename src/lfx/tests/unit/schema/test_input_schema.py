from typing import Literal, get_args, get_origin

import pytest
from lfx.inputs.inputs import DropdownInput, HandleInput, JSONInput
from lfx.io.schema import MAX_OPTIONS_FOR_TOOL_ENUM, create_input_schema, create_input_schema_from_dict
from lfx.schema.dotdict import dotdict


def _serialized_input(field_type):
    return [
        dotdict(
            {
                "name": "value",
                "display_name": "Value",
                "info": "",
                "required": True,
                "type": field_type,
                "value": None,
            }
        )
    ]


def test_create_input_schema_resolves_known_serialized_type():
    schema = create_input_schema_from_dict(_serialized_input("str"))

    assert schema.model_fields["value"].annotation is str


def test_create_input_schema_rejects_unknown_serialized_type():
    with pytest.raises(TypeError, match="Unsupported serialized field type"):
        create_input_schema_from_dict(_serialized_input("module.UnknownType"))


def _serialized_input_with_options(field_type, options):
    return [
        dotdict(
            {
                "name": "value",
                "display_name": "Value",
                "info": "",
                "required": True,
                "type": field_type,
                "value": None,
                "options": options,
                "is_list": False,
            }
        )
    ]


def test_create_input_schema_from_dict_builds_literal_from_options():
    """Serialized dropdown options should produce a Literal type without eval()."""
    schema = create_input_schema_from_dict(_serialized_input_with_options("str", ["a", "b", "c"]))

    annotation = schema.model_fields["value"].annotation
    assert get_origin(annotation) is Literal
    assert get_args(annotation) == ("a", "b", "c")


def test_create_input_schema_from_dict_literal_single_option():
    """A single option should still produce a valid Literal type."""
    schema = create_input_schema_from_dict(_serialized_input_with_options("str", ["only"]))

    annotation = schema.model_fields["value"].annotation
    assert get_origin(annotation) is Literal
    assert get_args(annotation) == ("only",)


def _dropdown_input(options):
    return DropdownInput(name="mode", display_name="Mode", info="Select mode", required=True, options=options)


def test_create_input_schema_builds_literal_from_options():
    """DropdownInput options should produce a Literal type without eval()."""
    schema = create_input_schema([_dropdown_input(["fast", "balanced", "thorough"])])

    annotation = schema.model_fields["mode"].annotation
    assert get_origin(annotation) is Literal
    assert get_args(annotation) == ("fast", "balanced", "thorough")


def test_create_input_schema_literal_single_option():
    """A single option should still produce a valid Literal type."""
    schema = create_input_schema([_dropdown_input(["only"])])

    annotation = schema.model_fields["mode"].annotation
    assert get_origin(annotation) is Literal
    assert get_args(annotation) == ("only",)


def test_literal_skipped_when_options_exceed_limit():
    """Over-limit option lists fall back to the base type instead of Literal."""
    many = [f"opt{i}" for i in range(MAX_OPTIONS_FOR_TOOL_ENUM + 1)]

    from_dict_schema = create_input_schema_from_dict(_serialized_input_with_options("str", many))
    assert from_dict_schema.model_fields["value"].annotation is str

    schema = create_input_schema([_dropdown_input(many)])
    assert schema.model_fields["mode"].annotation is str


def test_literal_skipped_when_options_empty():
    """An empty option list falls back to the base type instead of Literal."""
    from_dict_schema = create_input_schema_from_dict(_serialized_input_with_options("str", []))
    assert from_dict_schema.model_fields["value"].annotation is str

    schema = create_input_schema([_dropdown_input([])])
    assert schema.model_fields["mode"].annotation is str


@pytest.mark.parametrize("is_list", [False, True])
@pytest.mark.parametrize("serialized", [False, True])
def test_json_tool_input_accepts_objects(is_list, serialized):
    field = JSONInput(name="payload", required=True, is_list=is_list, tool_mode=True)
    schema = create_input_schema_from_dict([dotdict(field.to_dict())]) if serialized else create_input_schema([field])
    payload = [{"text": "hello", "nested": {"enabled": True}}] if is_list else {"short_description": "hello"}

    assert schema.model_validate({"payload": payload}).payload == payload
    prop = schema.model_json_schema()["properties"]["payload"]
    assert prop["type"] == ("array" if is_list else "object")
    if is_list:
        assert prop["items"]["type"] == "object"


@pytest.mark.parametrize("is_list", [False, True])
@pytest.mark.parametrize("serialized", [False, True])
def test_optional_json_tool_input_has_a_valid_empty_default(is_list, serialized):
    field = JSONInput(name="payload", is_list=is_list, tool_mode=True)
    schema = create_input_schema_from_dict([dotdict(field.to_dict())]) if serialized else create_input_schema([field])

    assert schema.model_validate({}).payload is None
    assert schema.model_validate({"payload": None}).payload is None
    assert schema.model_json_schema()["properties"]["payload"]["default"] is None


def test_legacy_serialized_data_input_accepts_an_object():
    field = JSONInput(name="payload", required=True).to_dict()
    field["_input_type"] = "DataInput"
    schema = create_input_schema_from_dict([dotdict(field)])

    assert schema.model_validate({"payload": {"title": "hello"}}).payload == {"title": "hello"}


@pytest.mark.parametrize("serialized", [False, True])
def test_other_handle_input_keeps_its_string_schema(serialized):
    field = HandleInput(name="payload", required=True, input_types=["CustomObject"])
    schema = create_input_schema_from_dict([dotdict(field.to_dict())]) if serialized else create_input_schema([field])

    assert schema.model_fields["payload"].annotation is str
