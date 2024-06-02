from typing import ClassVar, List, Optional

from langflow.template.field.base import Input, Output

from .custom_component import CustomComponent


class Component(CustomComponent):
    inputs: Optional[List[Input]] = None
    outputs: Optional[List[Output]] = None
    code_class_base_inheritance: ClassVar[str] = "Component"

    def set_attributes(self, params: dict):
        for key, value in params.items():
            if key in self.__dict__:
                raise ValueError(f"Key {key} already exists in {self.__class__.__name__}")
            setattr(self, key, value)
