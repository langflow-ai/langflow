from typing import Any

from langflow.schema.data import Data


def convert_to_langchain_type(value):
    from langflow.schema.message import Message

    if isinstance(value, dict):
        value = {key: convert_to_langchain_type(val) for key, val in value.items()}
    elif isinstance(value, list):
        value = [convert_to_langchain_type(v) for v in value]
    elif isinstance(value, Message):
        if "prompt" in value:
            value = value.load_lc_prompt()
        elif value.sender:
            value = value.to_lc_message()
        else:
            value = value.to_lc_document()
    elif isinstance(value, Data):
        value = value.to_lc_document() if "text" in value.data else value.data
    return value


def convert_to_langchain_types(io_dict: dict[str, Any]):
    converted = {}
    for key, value in io_dict.items():
        converted[key] = convert_to_langchain_type(value)
    return converted
