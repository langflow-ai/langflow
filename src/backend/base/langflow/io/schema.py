from typing import TYPE_CHECKING, List, Literal, Type

from pydantic import BaseModel, Field, create_model

from langflow.inputs.inputs import FieldTypes

_convert_field_type_to_type: dict[FieldTypes, Type] = {
    FieldTypes.TEXT: str,
    FieldTypes.INTEGER: int,
    FieldTypes.FLOAT: float,
    FieldTypes.BOOLEAN: bool,
    FieldTypes.DICT: dict,
    FieldTypes.NESTED_DICT: dict,
    FieldTypes.TABLE: dict,
    FieldTypes.FILE: str,
    FieldTypes.PROMPT: str,
}

if TYPE_CHECKING:
    from langflow.inputs.inputs import InputTypes


def create_input_schema(inputs: list["InputTypes"]) -> Type[BaseModel]:
    if not isinstance(inputs, list):
        raise ValueError("inputs must be a list of Inputs")
    fields = {}
    for input_model in inputs:
        # Create a Pydantic Field for each input field
        field_type = input_model.field_type
        if isinstance(field_type, FieldTypes):
            field_type = _convert_field_type_to_type[field_type]
        if hasattr(input_model, "options") and input_model.options:
            field_type = Literal[*input_model.options]
        if hasattr(input_model, "is_list") and input_model.is_list:
            field_type = List[field_type]
        field_dict = {
            "title": input_model.display_name or input_model.name.replace("_", " ").title(),
            "description": input_model.info or "",
        }
        if input_model.required is False:
            field_dict["default"] = input_model.value
        pydantic_field = Field(**field_dict)

        fields[input_model.name] = (field_type, pydantic_field)

    # Create and return the InputSchema model
    model = create_model("InputSchema", **fields)
    model.model_rebuild()
    return model
