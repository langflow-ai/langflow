from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, create_model

from langflow.inputs.inputs import FieldTypes
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
    FieldTypes.TAB: str,
}

if TYPE_CHECKING:
    from langflow.inputs.inputs import InputTypes


def create_input_schema(inputs: list["InputTypes"]) -> type[BaseModel]:
    if not isinstance(inputs, list):
        msg = "inputs must be a list of Inputs"
        raise TypeError(msg)
    fields = {}
    for input_model in inputs:
        # Create a Pydantic Field for each input field
        field_type = input_model.field_type
        if isinstance(field_type, FieldTypes):
            field_type = _convert_field_type_to_type[field_type]
        else:
            msg = f"Invalid field type: {field_type}"
            raise TypeError(msg)
        if hasattr(input_model, "options") and isinstance(input_model.options, list) and input_model.options:
            literal_string = f"Literal{input_model.options}"
            # validate that the literal_string is a valid literal

            field_type = eval(literal_string, {"Literal": Literal})  # noqa: S307
        if hasattr(input_model, "is_list") and input_model.is_list:
            field_type = list[field_type]  # type: ignore[valid-type]
        if input_model.name:
            name = input_model.name.replace("_", " ").title()
        elif input_model.display_name:
            name = input_model.display_name
        else:
            msg = "Input name or display_name is required"
            raise ValueError(msg)
        field_dict = {
            "title": name,
            "description": input_model.info or "",
        }
        if input_model.required is False:
            field_dict["default"] = input_model.value  # type: ignore[assignment]
        pydantic_field = Field(**field_dict)

        fields[input_model.name] = (field_type, pydantic_field)

    # Create and return the InputSchema model
    model = create_model("InputSchema", **fields)
    model.model_rebuild()
    return model


def create_input_schema_from_dict(inputs: list[dotdict], param_key: str | None = None) -> type[BaseModel]:
    if not isinstance(inputs, list):
        msg = "inputs must be a list of Inputs"
        raise TypeError(msg)
    fields = {}
    for input_model in inputs:
        # Create a Pydantic Field for each input field
        field_type = input_model.type
        if hasattr(input_model, "options") and isinstance(input_model.options, list) and input_model.options:
            literal_string = f"Literal{input_model.options}"
            # validate that the literal_string is a valid literal

            field_type = eval(literal_string, {"Literal": Literal})  # noqa: S307
        if hasattr(input_model, "is_list") and input_model.is_list:
            field_type = list[field_type]  # type: ignore[valid-type]
        if input_model.name:
            name = input_model.name.replace("_", " ").title()
        elif input_model.display_name:
            name = input_model.display_name
        else:
            msg = "Input name or display_name is required"
            raise ValueError(msg)
        field_dict = {
            "title": name,
            "description": input_model.info or "",
        }
        if input_model.required is False:
            field_dict["default"] = input_model.value  # type: ignore[assignment]
        pydantic_field = Field(**field_dict)

        fields[input_model.name] = (field_type, pydantic_field)

    # Wrap fields in a dictionary with the key as param_key
    if param_key is not None:
        # Create an inner model with the fields
        inner_model = create_model("InnerModel", **fields)

        # Ensure the model is wrapped correctly in a dictionary
        # model = create_model("InputSchema", **{param_key: (inner_model, Field(default=..., description=description))})
        model = create_model("InputSchema", **{param_key: (inner_model, ...)})
    else:
        # Create and return the InputSchema model
        model = create_model("InputSchema", **fields)

    model.model_rebuild()
    return model
