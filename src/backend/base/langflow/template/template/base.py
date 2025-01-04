from collections.abc import Callable
from typing import cast

from pydantic import BaseModel, Field, model_serializer

from langflow.inputs.inputs import InputTypes
from langflow.inputs.utils import instantiate_input
from langflow.template.field.base import Input
from langflow.utils.constants import DIRECT_TYPES


class Template(BaseModel):
    type_name: str = Field(serialization_alias="_type")
    fields: list[InputTypes]

    def process_fields(
        self,
        format_field_func: Callable | None = None,
    ) -> None:
        if format_field_func:
            for field in self.fields:
                format_field_func(field, self.type_name)

    def sort_fields(self) -> None:
        # first sort alphabetically
        # then sort fields so that fields that have .field_type in DIRECT_TYPES are first
        self.fields.sort(key=lambda x: x.name or "")
        self.fields.sort(
            key=lambda x: x.field_type in DIRECT_TYPES if hasattr(x, "field_type") else False, reverse=False
        )

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        result = handler(self)
        for field in self.fields:
            result[field.name] = field.model_dump(by_alias=True, exclude_none=True)

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Template":
        for key, value in data.copy().items():
            if key == "_type":
                data["type_name"] = value
                del data[key]
            else:
                value["name"] = key
                if "fields" not in data:
                    data["fields"] = []
                input_type = value.pop("_input_type", None)
                if input_type:
                    try:
                        input_ = instantiate_input(input_type, value)
                    except Exception as e:
                        msg = f"Error instantiating input {input_type}: {e}"
                        raise ValueError(msg) from e
                else:
                    input_ = Input(**value)

                data["fields"].append(input_)

        # Necessary for components with no inputs(?)
        if "fields" not in data:
            data["fields"] = []

        return cls(**data)

    # For backwards compatibility
    def to_dict(self, format_field_func=None):
        self.process_fields(format_field_func)
        self.sort_fields()
        return self.model_dump(by_alias=True, exclude_none=True, exclude={"fields"})

    def add_field(self, field: Input) -> None:
        self.fields.append(field)

    def get_field(self, field_name: str) -> Input:
        """Returns the field with the given name."""
        field = next((field for field in self.fields if field.name == field_name), None)
        if field is None:
            msg = f"Field {field_name} not found in template {self.type_name}"
            raise ValueError(msg)
        return cast("Input", field)

    def update_field(self, field_name: str, field: Input) -> None:
        """Updates the field with the given name."""
        for idx, template_field in enumerate(self.fields):
            if template_field.name == field_name:
                self.fields[idx] = field
                return
        msg = f"Field {field_name} not found in template {self.type_name}"
        raise ValueError(msg)

    def upsert_field(self, field_name: str, field: Input) -> None:
        """Updates the field with the given name or adds it if it doesn't exist."""
        try:
            self.update_field(field_name, field)
        except ValueError:
            self.add_field(field)
