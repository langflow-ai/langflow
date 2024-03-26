from typing import Callable, Union

from pydantic import BaseModel, model_serializer

from langflow.template.field.base import TemplateField
from langflow.utils.constants import DIRECT_TYPES


class Template(BaseModel):
    type_name: str
    fields: list[TemplateField]

    def process_fields(
        self,
        format_field_func: Union[Callable, None] = None,
    ):
        if format_field_func:
            for field in self.fields:
                format_field_func(field, self.type_name)

    def sort_fields(self):
        # first sort alphabetically
        # then sort fields so that fields that have .field_type in DIRECT_TYPES are first
        self.fields.sort(key=lambda x: x.name)
        self.fields.sort(key=lambda x: x.field_type in DIRECT_TYPES, reverse=False)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        result = handler(self)
        for field in self.fields:
            result[field.name] = field.model_dump(by_alias=True, exclude_none=True)
        result["_type"] = result.pop("type_name")
        return result

    # For backwards compatibility
    def to_dict(self, format_field_func=None):
        self.process_fields(format_field_func)
        self.sort_fields()
        return self.model_dump(by_alias=True, exclude_none=True, exclude={"fields"})

    def add_field(self, field: TemplateField) -> None:
        self.fields.append(field)

    def get_field(self, field_name: str) -> TemplateField:
        """Returns the field with the given name."""
        field = next((field for field in self.fields if field.name == field_name), None)
        if field is None:
            raise ValueError(f"Field {field_name} not found in template {self.type_name}")
        return field

    def update_field(self, field_name: str, field: TemplateField) -> None:
        """Updates the field with the given name."""
        for idx, template_field in enumerate(self.fields):
            if template_field.name == field_name:
                self.fields[idx] = field
                return
        raise ValueError(f"Field {field_name} not found in template {self.type_name}")

    def upsert_field(self, field_name: str, field: TemplateField) -> None:
        """Updates the field with the given name or adds it if it doesn't exist."""
        try:
            self.update_field(field_name, field)
        except ValueError:
            self.add_field(field)
