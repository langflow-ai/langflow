from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, create_model

from langflow.inputs.inputs import FieldTypes

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
}

if TYPE_CHECKING:
    from langflow.inputs.inputs import InputTypes


def create_input_schema(inputs: list["InputTypes"]) -> type[BaseModel]:
    if not isinstance(inputs, list):
        raise TypeError("inputs must be a list of Inputs")
    fields = {}
    for input_model in inputs:
        # Create a Pydantic Field for each input field
        field_type = input_model.field_type
        if isinstance(field_type, FieldTypes):
            field_type = _convert_field_type_to_type[field_type]
        if hasattr(input_model, "options") and isinstance(input_model.options, list) and input_model.options:
            literal_string = f"Literal{input_model.options}"
            # validate that the literal_string is a valid literal

            field_type = eval(literal_string, {"Literal": Literal})  # type: ignore
        if hasattr(input_model, "is_list") and input_model.is_list:
            field_type = list[field_type]  # type: ignore
        if input_model.name:
            name = input_model.name.replace("_", " ").title()
        elif input_model.display_name:
            name = input_model.display_name
        else:
            raise ValueError("Input name or display_name is required")
        field_dict = {
            "title": name,
            "description": input_model.info or "",
        }
        if input_model.required is False:
            field_dict["default"] = input_model.value  # type: ignore
        pydantic_field = Field(**field_dict)

        fields[input_model.name] = (field_type, pydantic_field)

    # Create and return the InputSchema model
    model = create_model("InputSchema", **fields)
    model.model_rebuild()
    return model
