import pytest
from lfx.io.schema import create_input_schema_from_dict
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


def test_create_input_schema_builds_literal_from_options():
    """Options should produce a Literal type without using eval()."""
    from typing import Literal, get_args

    schema = create_input_schema_from_dict(_serialized_input_with_options("str", ["a", "b", "c"]))

    annotation = schema.model_fields["value"].annotation
    assert get_origin(annotation) is Literal
    assert set(get_args(annotation)) == {"a", "b", "c"}


def test_create_input_schema_literal_single_option():
    """A single option should still produce a valid Literal type."""
    from typing import Literal, get_args

    schema = create_input_schema_from_dict(_serialized_input_with_options("str", ["only"]))

    annotation = schema.model_fields["value"].annotation
    assert get_origin(annotation) is Literal
    assert get_args(annotation) == ("only",)
