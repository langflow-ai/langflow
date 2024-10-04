from typing import Any

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, create_model


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(populate_by_name=True)


def _get_type_annotation(type_str: str, multiple: bool) -> type:
    type_mapping = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list[Any],
        "dict": dict[str, Any],
    }
    try:
        base_type = type_mapping[type_str]
    except KeyError as e:
        msg = f"Invalid type: {type_str}"
        raise ValueError(msg) from e
    if multiple:
        return list[base_type]
    return base_type  # type: ignore


def build_model_from_schema(schema: list[dict[str, Any]]) -> type[PydanticBaseModel]:
    fields = {}
    for field in schema:
        field_name = field["name"]
        field_type_str = field["type"]
        default_value = field["default"]
        description = field.get("description", "")
        multiple = field.get("multiple", False)
        field_type_annotation = _get_type_annotation(field_type_str, multiple)
        fields[field_name] = (field_type_annotation, Field(default=default_value, description=description))
    return create_model("OutputModel", **fields)
