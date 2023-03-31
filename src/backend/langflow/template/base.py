from abc import ABC
from typing import Any, Union

from pydantic import BaseModel


class FieldCreator(BaseModel, ABC):
    field_type: str = "str"
    required: bool = False
    placeholder: str = ""
    is_list: bool = False
    show: bool = True
    multiline: bool = False
    value: Any = None
    suffixes: list[str] = []
    file_types: list[str] = []
    content: Union[str, None] = None
    password: bool = False
    # _name will be used to store the name of the field
    # in the template
    name: str = ""

    def to_dict(self):
        result = self.dict()
        # Remove key if it is None
        for key in list(result.keys()):
            if result[key] is None or result[key] == []:
                del result[key]
        result["type"] = result.pop("field_type")
        result["list"] = result.pop("is_list")

        if result.get("file_types"):
            result["fileTypes"] = result.pop("file_types")

        if self.field_type == "file":
            result["content"] = self.content
        return result


class Field(FieldCreator):
    pass


class Template(BaseModel):
    type_name: str
    fields: list[Field]

    def to_dict(self):
        result = {field.name: field.to_dict() for field in self.fields}
        result["_type"] = self.type_name  # type: ignore
        return result


class FrontendNode(BaseModel):
    template: Template
    description: str
    base_classes: list
    name: str = ""

    def to_dict(self):
        return {
            self.name: {
                "template": self.template.to_dict(),
                "description": self.description,
                "base_classes": self.base_classes,
            }
        }
