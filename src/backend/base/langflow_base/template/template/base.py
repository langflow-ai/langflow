from typing import Callable, Optional, Union

from langflow_base.template.field.base import TemplateField
from langflow_base.utils.constants import DIRECT_TYPES
from pydantic import BaseModel


class Template(BaseModel):
    type_name: str
    fields: list[TemplateField]

    def process_fields(
        self,
        name: Optional[str] = None,
        format_field_func: Union[Callable, None] = None,
    ):
        if format_field_func:
            for field in self.fields:
                format_field_func(field, name)

    def sort_fields(self):
        # first sort alphabetically
        # then sort fields so that fields that have .field_type in DIRECT_TYPES are first
        self.fields.sort(key=lambda x: x.name)
        self.fields.sort(key=lambda x: x.field_type in DIRECT_TYPES, reverse=False)

    def to_dict(self, format_field_func=None):
        self.process_fields(self.type_name, format_field_func)
        self.sort_fields()
        result = {field.name: field.to_dict() for field in self.fields}
        result["_type"] = self.type_name  # type: ignore
        return result

    def add_field(self, field: TemplateField) -> None:
        self.fields.append(field)
