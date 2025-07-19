from typing import Any, TypedDict

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, create_model

TRUE_VALUES = ["true", "1", "t", "y", "yes"]


class SchemaField(TypedDict):
    name: str
    type: str
    description: str
    multiple: bool


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(populate_by_name=True)


def _get_type_annotation(type_str: str, *, multiple: bool) -> type:
    type_mapping = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "boolean": bool,
        "list": list[Any],
        "dict": dict[str, Any],
        "number": float,
        "text": str,
    }
    try:
        base_type = type_mapping[type_str]
    except KeyError as e:
        msg = f"Invalid type: {type_str}"
        raise ValueError(msg) from e
    if multiple:
        return list[base_type]  # type: ignore[valid-type]
    return base_type  # type: ignore[return-value]


def build_model_from_schema(schema: list[SchemaField]) -> type[PydanticBaseModel]:
    fields = {}
    for field in schema:
        field_name = field["name"]
        field_type_str = field["type"]
        description = field.get("description", "")
        multiple = field.get("multiple", False)
        multiple = coalesce_bool(multiple)
        field_type_annotation = _get_type_annotation(field_type_str, multiple=multiple)
        fields[field_name] = (field_type_annotation, Field(description=description))
    return create_model("OutputModel", **fields)


def coalesce_bool(value: Any) -> bool:
    """Coalesces the given value into a boolean.

    Args:
        value (Any): The value to be coalesced.

    Returns:
        bool: The coalesced boolean value.

    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in TRUE_VALUES
    if isinstance(value, int):
        return bool(value)
    return False