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

    fields = {}
    for input_model in inputs:
        field_type = input_model.field_type
        if isinstance(field_type, FieldTypes):
            field_type = _convert_field_type_to_type[field_type]
        if hasattr(input_model, "options") and isinstance(input_model.options, list) and input_model.options:
            field_type = Literal[input_model.options]
        if hasattr(input_model, "is_list") and input_model.is_list:
            field_type = list[field_type]
        name = input_model.name.replace("_", " ").title() if input_model.name else input_model.display_name
        if not name:
            raise ValueError("Input name or display_name is required")
        field_dict = {"title": name, "description": input_model.info or ""}
        if input_model.required is False:
            field_dict["default"] = input_model.value
        fields[input_model.name] = (field_type, Field(**field_dict))

    model = create_model("InputSchema", **fields)
    model.model_rebuild()
    return model


def create_input_schema_from_dict(inputs: list[dotdict], param_key: str | None = None) -> type[BaseModel]:
    if not isinstance(inputs, list):
        raise TypeError("inputs must be a list of Inputs")

    fields = {}
    for input_model in inputs:
        field_type = input_model.type
        if hasattr(input_model, "options") and isinstance(input_model.options, list) and input_model.options:
            field_type = Literal[input_model.options]
        if hasattr(input_model, "is_list") and input_model.is_list:
            field_type = list[field_type]
        name = input_model.name.replace("_", " ").title() if input_model.name else input_model.display_name
        if not name:
            raise ValueError("Input name or display_name is required")
        field_dict = {"title": name, "description": input_model.info or ""}
        if input_model.required is False:
            field_dict["default"] = input_model.value
        fields[input_model.name] = (field_type, Field(**field_dict))

    if param_key is not None:
        inner_model = create_model("InnerModel", **fields)
        model = create_model("InputSchema", **{param_key: (inner_model, ...)})
    else:
        model = create_model("InputSchema", **fields)

    model.model_rebuild()
    return model
