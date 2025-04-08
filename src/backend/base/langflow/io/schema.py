from typing import Literal, Union, get_args, get_origin

from pydantic import BaseModel, Field, create_model

from langflow.inputs.inputs import BoolInput, DictInput, FieldTypes, FloatInput, InputTypes, IntInput, MessageTextInput
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


_convert_type_to_field_type = {
    str: MessageTextInput,
    int: IntInput,
    float: FloatInput,
    bool: BoolInput,
    dict: DictInput,
    list: MessageTextInput,
}


def schema_to_langflow_inputs(schema: type[BaseModel]) -> list["InputTypes"]:
    """Given a Pydantic schema, convert its fields to Langflow input definitions."""
    inputs = []
    for field_name, model_field in schema.model_fields.items():
        # Start with the field's annotation type
        field_type = model_field.annotation
        is_list = False
        options = None

        # If the field is a list, record that and extract its inner type.
        if get_origin(field_type) is list:
            is_list = True
            field_type = get_args(field_type)[0]

        # If the field type is a Literal, extract its allowed values.
        if get_origin(field_type) is Literal:
            options = list(get_args(field_type))
            # Optionally, set field_type to the type of the literal values.
            if options:
                field_type = type(options[0])

        # Handle Union types (e.g., Optional fields)
        if get_origin(field_type) is Union:
            # Get the first non-None type from the Union
            field_type = next(t for t in get_args(field_type) if t is not type(None))

        # Convert the Python type to the Langflow field type using our reverse mapping.
        try:
            langflow_field_type = _convert_type_to_field_type[field_type]
        except KeyError as e:
            msg = f"Unsupported field type: {field_type}"
            raise TypeError(msg) from e

        # Get metadata from the Pydantic Field.
        title = model_field.title or field_name.replace("_", " ").title()
        description = model_field.description or ""
        required = model_field.is_required()

        # Construct the Langflow input.
        input_obj = langflow_field_type(
            display_name=title,
            name=field_name,
            info=description,
            required=required,
            is_list=is_list,
        )
        inputs.append(input_obj)
    return inputs


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
