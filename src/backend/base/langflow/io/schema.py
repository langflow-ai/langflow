from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, create_model

from langflow.inputs.inputs import FieldTypes, InputTypes
from langflow.schema.dotdict import dotdict

_convert_field_type_to_type: dict[FieldTypes, type] = {
    FieldTypes.TEXT: str,
    FieldTypes.INTEGER: int,
    FieldTypes.FLOAT: float,
    FieldTypes.BOOLEAN: bool,
    FieldTypes.DICT: dict,
    FieldTypes.NESTED_DICT: dict,
    FieldTypes.TABLE: dict,
    FieldTypes.FILE: str,
    FieldTypes.PROMPT: str,
    FieldTypes.CODE: str,
    FieldTypes.OTHER: str,
}

if TYPE_CHECKING:
    from langflow.inputs.inputs import InputTypes


def create_input_schema(inputs: list[InputTypes]) -> type[BaseModel]:
    if not isinstance(inputs, list):
        raise TypeError("inputs must be a list of Inputs")

    fields = {
        inp.name: (
            (
                list[field_type] if getattr(inp, "is_list", False) else field_type,
                Field(
                    title=(inp.name.replace("_", " ").title() if inp.name else inp.display_name),
                    description=(inp.info or ""),
                    default=(inp.value if not inp.required else ...),
                ),
            )
            if (
                (
                    field_type := _convert_field_type_to_type[inp.field_type]
                    if isinstance(inp.field_type, FieldTypes)
                    else inp.field_type
                )
                and hasattr(inp, "options")
                and isinstance(inp.options, list)
                and inp.options
                and not (field_type := eval(f"Literal{inp.options}", {"Literal": Literal}))
            )
            else TypeError(f"Invalid field type: {field_type}")
        )
        for inp in inputs
    }

    model = create_model("InputSchema", **fields)
    model.model_rebuild()
    return model


def create_input_schema_from_dict(inputs: list[dotdict], param_key: str | None = None) -> type[BaseModel]:
    if not isinstance(inputs, list):
        raise TypeError("inputs must be a list of Inputs")

    fields = {
        inp.name: (
            (
                list[field_type] if getattr(inp, "is_list", False) else field_type,
                Field(
                    title=(inp.name.replace("_", " ").title() if inp.name else inp.display_name),
                    description=(inp.info or ""),
                    default=(inp.value if not inp.required else ...),
                ),
            )
            if (
                (field_type := inp.type)
                and hasattr(inp, "options")
                and isinstance(inp.options, list)
                and inp.options
                and not (field_type := eval(f"Literal{inp.options}", {"Literal": Literal}))
            )
            else TypeError(f"Invalid field type: {field_type}")
        )
        for inp in inputs
    }

    model = create_model(
        "InputSchema", **{param_key: (create_model("InnerModel", **fields), ...)} if param_key else fields
    )
    model.model_rebuild()
    return model
