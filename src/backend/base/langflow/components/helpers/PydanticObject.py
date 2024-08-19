from typing import Any, Dict, Tuple, Type
from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.inputs.inputs import MessageInput, MessageTextInput
from langflow.io import DataInput, MultilineInput, Output, StrInput
from langchain_core.pydantic_v1 import Field, create_model
from langflow.helpers.base_model import BaseModel


class PydanticObjectComponent(Component):
    display_name = "Pydantic Object"
    description = "Helper to create a Pydantic Object to be used in an Output Parser."
    icon = "python"
    name = "PydanticObject"

    inputs = [
        MultilineInput(
            name="object_fields",
            display_name="Fields",
            info="The fields, types, and descriptions for your pydantic object. Format: `field_name,field_type,field_description`",
        ),
    ]

    outputs = [
        Output(display_name="Object", name="object", method="create_pydantic_object"),
    ]

    def create_pydantic_object(self) -> Type[BaseModel]:
        object_fields = self.inputs["object_fields"]
        fields = object_fields.split("\n")
        field_attrs = []
        for field in fields:
            field_name, field_type, field_description = field.split(",")
            field_attrs.append((field_name, field_type, field_description))

        def create_pydantic_model(
            fields: Tuple[str, str, str]
        ) -> Type[BaseModel]:
            # Convert the type strings to actual Python types
            type_mapping = {
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "bytes": bytes,
                "None": type(None),
                "Any": object,
            }

            try:
                parsed_fields = {
                    field_name: (type_mapping.get(field_type), Field(description=description))
                    for field_name, field_type, description in fields
                }
            except ValueError as e:
                raise ValueError(
                    f"Error parsing field type(s): {e}.\nAllowed types: {type_mapping.keys()}"
                )

            # Create the model using create_model
            model = create_model("MyPydanticModel", **parsed_fields)
            return model

        Model = create_pydantic_model(object_fields)
        print("FRAZIER - Model")
        print(Model)
        return Model
