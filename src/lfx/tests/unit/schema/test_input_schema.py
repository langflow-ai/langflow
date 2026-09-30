from typing import Literal, get_args, get_origin

import pytest
from lfx.inputs.inputs import DropdownInput
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
