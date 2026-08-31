import os
from unittest.mock import Mock

import pytest
from langflow.io.schema import create_input_schema_from_dict
from lfx.schema.dotdict import dotdict


def test_create_schema():
    sample_input = [
        {
            "_input_type": "MultilineInput",
            "advanced": False,
            "display_name": "Chat Input - Text",
            "dynamic": False,
            "info": "Message to be passed as input.",
            "input_types": ["Message"],
            "list": False,
            "load_from_db": False,
            "multiline": True,
            "name": "ChatInput-xNZ0a|input_value",
            "placeholder": "",
            "required": False,
            "show": True,
            "title_case": False,
            "tool_mode": True,
            "trace_as_input": True,
            "trace_as_metadata": True,
            "type": "str",
            "value": "add 1+1",
        }
    ]
    # convert to dotdict
    # change the key type
    sample_input = [dotdict(field) for field in sample_input]
    schema = create_input_schema_from_dict(sample_input)
    assert schema is not None


@pytest.mark.parametrize(
    ("serialized_type", "expected_type"),
    [
        ("str", str),
        ("int", int),
        ("float", float),
        ("bool", bool),
        ("boolean", bool),
        ("dict", dict),
        ("NestedDict", dict),
        ("sortableList", list),
        ("actionPicker", list),
        ("duration", dict),
        ("connect", str),
        ("auth", dict),
        ("file", str),
        ("prompt", str),
        ("mustache", str),
        ("code", str),
        ("other", str),
        ("table", dict),
        ("link", str),
        ("slider", float),
        ("tab", str),
        ("query", str),
        ("tools", list),
        ("mcp", dict),
        ("model", list),
        ("data_display", dict),
        ("knowledge_backend", str),
    ],
)
def test_create_schema_resolves_serialized_field_types(serialized_type, expected_type):
    sample_input = [
        dotdict(
            {
                "name": "value",
                "display_name": "Value",
                "info": "",
                "required": True,
                "type": serialized_type,
                "value": None,
            }
        )
    ]

    schema = create_input_schema_from_dict(sample_input)

    assert schema.model_fields["value"].annotation is expected_type


def test_create_schema_rejects_forward_ref_expressions(monkeypatch):
    system_mock = Mock(side_effect=AssertionError("untrusted expression was evaluated"))
    monkeypatch.setattr(os, "system", system_mock)
    sample_input = [
        dotdict(
            {
                "name": "value",
                "display_name": "Value",
                "info": "",
                "required": True,
                "type": "(__import__('os').system('not-a-command'), str)[1]",
                "value": None,
            }
        )
    ]

    with pytest.raises(TypeError, match="Unsupported serialized field type"):
        create_input_schema_from_dict(sample_input)

    system_mock.assert_not_called()
