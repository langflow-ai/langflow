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
        input_model.name: (
            _convert_field_type_to_type.get(input_model.field_type, str),
            Field(
                title=input_model.name.replace("_", " ").title() if input_model.name else input_model.display_name,
                description=input_model.info or "",
                default=input_model.value if not input_model.required else ...,
            ),
        )
        for input_model in inputs
    }

    return create_model("InputSchema", **fields).model_rebuild()


def create_input_schema_from_dict(inputs: list[dotdict], param_key: str | None = None) -> type[BaseModel]:
    if not isinstance(inputs, list):
        raise TypeError("inputs must be a list of Inputs")

    fields = {
        input_model.name: (
            eval(f"Literal{input_model.options}", {"Literal": Literal})
            if hasattr(input_model, "options") and isinstance(input_model.options, list) and input_model.options
            else input_model.type,
            Field(
                title=input_model.name.replace("_", " ").title() if input_model.name else input_model.display_name,
                description=input_model.info or "",
                default=input_model.value if not input_model.required else ...,
            ),
        )
        for input_model in inputs
    }

    if param_key:
        inner_model = create_model("InnerModel", **fields)
        return create_model("InputSchema", **{param_key: (inner_model, ...)}).model_rebuild()
    return create_model("InputSchema", **fields).model_rebuild()
