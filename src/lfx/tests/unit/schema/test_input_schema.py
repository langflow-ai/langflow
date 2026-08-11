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


def _serialized_input_with_options(options):
    return [
        dotdict(
            {
                "name": "mode",
                "display_name": "Mode",
                "info": "Select mode",
                "required": True,
                "type": "str",
                "value": None,
                "options": options,
                "is_list": False,
            }
        )
    ]


def test_create_input_schema_with_options_builds_literal_type():
    """Dropdown options should produce a Literal type without using eval()."""
    schema = create_input_schema_from_dict(
        _serialized_input_with_options(["fast", "balanced", "thorough"])
    )

    annotation = schema.model_fields["mode"].annotation
    # Literal types expose their values via __args__
    assert annotation.__args__ == ("fast", "balanced", "thorough")


def test_create_input_schema_with_single_option_builds_literal_type():
    """A single option should still produce a valid Literal type."""
    schema = create_input_schema_from_dict(
        _serialized_input_with_options(["only"])
    )

    annotation = schema.model_fields["mode"].annotation
    assert annotation.__args__ == ("only",)


def test_create_input_schema_with_many_options_skips_literal():
    """When options exceed MAX_OPTIONS_FOR_TOOL_ENUM, no Literal is built."""
    from lfx.io.schema import MAX_OPTIONS_FOR_TOOL_ENUM

    many_options = [f"opt{i}" for i in range(MAX_OPTIONS_FOR_TOOL_ENUM + 1)]
    schema = create_input_schema_from_dict(
        _serialized_input_with_options(many_options)
    )

    annotation = schema.model_fields["mode"].annotation
    # Should fall back to the base str type, not a Literal
    assert annotation is str
