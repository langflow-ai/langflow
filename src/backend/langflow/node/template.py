from typing import Any
from pydantic import BaseModel


class Field(BaseModel):
    field_type: str = "str"
    required: bool = False
    placeholder: str = ""
    is_list: bool = False
    show: bool = True
    multiline: bool = False
    value: Any = None
    # _name will be used to store the name of the field
    # in the template
    name: str = None

    def to_dict(self):
        return self.dict()


class Template(BaseModel):
    type_name: str
    fields: list[Field]

    def to_dict(self):
        result = {field.name: field.to_dict() for field in self.fields}
        result["_type"] = self.type_name
        return result


class FrontendNode(BaseModel):
    template: Template
    description: str
    base_classes: list
    _name: str = None

    def to_dict(self):
        return {
            self._name: {
                "template": self.template.to_dict(),
                "description": self.description,
                "base_classes": self.base_classes,
            }
        }
