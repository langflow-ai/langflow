import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import Field, create_model

from langflow.helpers.base_model import BaseModel


def create_tool_coroutine(tool_name: str, arg_schema: type[BaseModel], session) -> Callable[..., Awaitable]:
    async def tool_coroutine(*args, **kwargs):
        # Get field names from the model (preserving order)
        field_names = list(arg_schema.__fields__.keys())
        provided_args = {}
        # Map positional arguments to their corresponding field names
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        # Merge in keyword arguments
        provided_args.update(kwargs)
        # Validate input and fill defaults for missing optional fields
        try:
            validated = arg_schema.parse_obj(provided_args)
        except Exception as e:
            msg = f"Invalid input: {e}"
            raise ValueError(msg) from e
        return await session.call_tool(tool_name, arguments=validated.dict())

    return tool_coroutine


def create_tool_func(tool_name: str, arg_schema: type[BaseModel], session) -> Callable[..., str]:
    def tool_func(*args, **kwargs):
        field_names = list(arg_schema.__fields__.keys())
        provided_args = {}
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        provided_args.update(kwargs)
        try:
            validated = arg_schema.parse_obj(provided_args)
        except Exception as e:
            msg = f"Invalid input: {e}"
            raise ValueError(msg) from e
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(session.call_tool(tool_name, arguments=validated.dict()))

    return tool_func


def create_input_schema_from_json_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Converts a JSON schema into a Pydantic model dynamically.

    Fields not listed as required are wrapped in Optional[...] and default to None if not provided.

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
        # Determine the base type from the JSON schema type string.
        field_type_str = field_def.get("type", "str")  # Defaults to string if not specified.
        base_type = {
            "string": str,
            "str": str,
            "integer": int,
            "int": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }.get(field_type_str, Any)

        field_metadata = {"description": field_def.get("description", "")}

        # For non-required fields, wrap the type in Optional[...] and set a default value.
        if field_name not in required_fields:
            #base_type = base_type | None
            base_type = base_type
            field_metadata["default"] = field_def.get("default", None)

        fields[field_name] = (base_type, Field(**field_metadata))

    return create_model("InputSchema", **fields)
