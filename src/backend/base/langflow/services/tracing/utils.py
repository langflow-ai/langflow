from typing import Any, Dict

from langflow.schema.data import Data


def convert_to_langchain_type(value):
    from langflow.schema.message import Message

    if isinstance(value, dict):
        return {k: convert_to_langchain_type(v) for k, v in value.items()}
    if isinstance(value, list):
        return [convert_to_langchain_type(v) for v in value]
    if isinstance(value, Message):
        if "prompt" in value:
            return value.load_lc_prompt()
        if value.sender:
            return value.to_lc_message()
        return value.to_lc_document()
    if isinstance(value, Data):
        return value.to_lc_document() if "text" in value.data else value.data
    return value


def convert_to_langchain_types(io_dict: Dict[str, Any]):
    converted = {}
    for key, value in io_dict.items():
        converted[key] = convert_to_langchain_type(value)
    return converted
