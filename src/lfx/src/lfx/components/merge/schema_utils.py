from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model


def json_schema_to_pydantic_model(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """Convert an MCP JSON Schema object into a dynamic Pydantic model."""
    model_name = _to_model_name(name)
    properties = schema.get("properties") if isinstance(schema, dict) else None
    required = set(schema.get("required") or []) if isinstance(schema, dict) else set()
    fields: dict[str, tuple[Any, Any]] = {}

    for key, raw_prop_schema in (properties or {}).items():
        prop_schema = raw_prop_schema if isinstance(raw_prop_schema, dict) else {}

        annotation = _schema_to_annotation(f"{model_name}_{_to_model_name(key)}", prop_schema)
        description = prop_schema.get("description")
        is_required = key in required

        if not is_required:
            annotation = annotation | None

        default = ... if is_required else None
        if description:
            fields[key] = (annotation, Field(default=default, description=str(description)))
        else:
            fields[key] = (annotation, default)

    return create_model(model_name, **fields)


def create_dispatch_schema(tool_names: list[str]) -> type[BaseModel]:
    tool_description = "The MCP tool name to execute."
    tool_name_annotation: Any = str
    if tool_names:
        normalized_tool_names = sorted({name for name in tool_names if name})
        listed = ", ".join(normalized_tool_names)
        if listed:
            tool_description = f"{tool_description} Available tools: {listed}."
            tool_name_annotation = Literal.__getitem__(tuple(normalized_tool_names))

    return create_model(
        "MergeMcpDispatchInput",
        tool_name=(tool_name_annotation, Field(description=tool_description)),
        arguments=(
            dict[str, Any] | None,
            Field(default=None, description="Arguments to pass to the selected tool."),
        ),
    )


def _schema_to_annotation(name: str, schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type") if isinstance(schema, dict) else None

    enum_values = schema.get("enum") if isinstance(schema, dict) else None
    if isinstance(enum_values, list) and enum_values and all(isinstance(value, str) for value in enum_values):
        return Literal.__getitem__(tuple(enum_values))

    if schema_type == "string":
        return str
    if schema_type == "number":
        return float
    if schema_type == "integer":
        return int
    if schema_type == "boolean":
        return bool

    if schema_type == "array":
        items_schema = schema.get("items") if isinstance(schema, dict) else None
        if isinstance(items_schema, dict):
            return list[_schema_to_annotation(f"{name}Item", items_schema)]
        return list[Any]

    if schema_type == "object":
        nested_properties = schema.get("properties") if isinstance(schema, dict) else None
        if isinstance(nested_properties, dict) and nested_properties:
            nested_schema: dict[str, Any] = {
                "type": "object",
                "properties": nested_properties,
            }
            nested_required = schema.get("required") if isinstance(schema, dict) else None
            if isinstance(nested_required, list):
                nested_schema["required"] = [str(value) for value in nested_required]

            return json_schema_to_pydantic_model(f"{name}Object", nested_schema)
        return dict[str, Any]

    return Any


def _to_model_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_")
    if not cleaned:
        return "MergeSchema"

    parts = [part for part in cleaned.split("_") if part]
    pascal = "".join(part[:1].upper() + part[1:] for part in parts)
    if not pascal:
        pascal = "MergeSchema"
    if pascal[0].isdigit():
        pascal = f"M{pascal}"
    return pascal
