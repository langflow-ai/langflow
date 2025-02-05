import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import Field, create_model

from langflow.helpers.base_model import BaseModel


def create_tool_coroutine(tool_name: str, arg_schema: type[BaseModel], session) -> Callable[[dict], Awaitable]:
    async def tool_coroutine(*args, **kwargs):
        fields = arg_schema.model_fields.keys()
        expected_field_count = len(fields)
        if len(args) + len(kwargs) != expected_field_count:
            msg = f"{expected_field_count} arguments are required. Received: {args} {kwargs}"
            raise ValueError(msg)
        arg_dict = dict(zip(fields, args, strict=False))
        arg_dict.update(kwargs)
        return await session.call_tool(tool_name, arguments=arg_dict)

    return tool_coroutine


def create_tool_func(tool_name: str, session) -> Callable[..., str]:
    def tool_func(**kwargs):
        if len(kwargs) == 0:
            msg = f"at least one named argument is required {kwargs}"
            raise ValueError(msg)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(session.call_tool(tool_name, arguments=kwargs))

    return tool_func


def create_input_schema_from_json_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Converts a JSON schema into a Pydantic model dynamically.

    :param schema: The JSON schema as a dictionary.
    :return: A Pydantic model class.
    """
    if schema.get("type") != "object":
        msg = "JSON schema must be of type 'object' at the root level."
        raise ValueError(msg)

    fields = {}
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_def in properties.items():
        # Extract type
        field_type_str = field_def.get("type", "str")  # Default to string type if not specified
        field_type = {
            "string": str,
            "str": str,
            "integer": int,
            "int": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }.get(field_type_str, Any)

        # Extract description and default if present
        field_metadata = {"description": field_def.get("description", "")}
        if field_name not in required_fields:
            field_metadata["default"] = field_def.get("default", None)

        # Create Pydantic field
        fields[field_name] = (field_type, Field(**field_metadata))

    # Dynamically create the model
    return create_model("InputSchema", **fields)
