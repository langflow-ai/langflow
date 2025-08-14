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
