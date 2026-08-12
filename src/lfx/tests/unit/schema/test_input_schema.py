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
