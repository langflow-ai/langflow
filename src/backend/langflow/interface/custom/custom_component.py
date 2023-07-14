import ast
from typing import Callable, Optional
from fastapi import HTTPException
from langflow.interface.custom.constants import LANGCHAIN_BASE_TYPES
from langflow.interface.custom.component import Component

from langflow.utils import validate


class CustomComponent(Component):
    code: Optional[str]
    field_config: dict = {}
    code_class_base_inheritance = "CustomComponent"
    function_entrypoint_name = "build"
    function: Optional[Callable] = None
    return_type_valid_list = list(LANGCHAIN_BASE_TYPES.keys())

    def __init__(self, **data):
        super().__init__(**data)

    def _class_template_validation(self, code: str) -> bool:
        if not code:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": self.ERROR_CODE_NULL,
                    "traceback": "",
                },
            )

        # TODO: build logic
        return True

    def is_check_valid(self) -> bool:
        return self._class_template_validation(self.code)

    def get_code_tree(self, code: str):
        return super().get_code_tree(code)

    @property
    def get_function_entrypoint_args(self) -> str:
        tree = self.get_code_tree(self.code)

        component_classes = [
            cls
            for cls in tree["classes"]
            if self.code_class_base_inheritance in cls["bases"]
        ]
        if not component_classes:
            return ""

        # Assume the first Component class is the one we're interested in
        component_class = component_classes[0]
        build_methods = [
            method
            for method in component_class["methods"]
            if method["name"] == self.function_entrypoint_name
        ]

        if not build_methods:
            return ""

        build_method = build_methods[0]

        return build_method["args"]

    @property
    def get_function_entrypoint_return_type(self) -> str:
        tree = self.get_code_tree(self.code)

        component_classes = [
            cls
            for cls in tree["classes"]
            if self.code_class_base_inheritance in cls["bases"]
        ]
        if not component_classes:
            return ""

        # Assume the first Component class is the one we're interested in
        component_class = component_classes[0]
        build_methods = [
            method
            for method in component_class["methods"]
            if method["name"] == self.function_entrypoint_name
        ]

        if not build_methods:
            return ""

        build_method = build_methods[0]

        return build_method["return_type"]

    @property
    def get_template_config(self) -> dict:
        extra_attributes = {}  # self.get_extra_attributes
        template_config = {}

        if "field_config" in extra_attributes:
            template_config["field_config"] = ast.literal_eval(
                extra_attributes["field_config"]
            )
        if "display_name" in extra_attributes:
            template_config["display_name"] = ast.literal_eval(
                extra_attributes["display_name"]
            )
        if "description" in extra_attributes:
            template_config["description"] = ast.literal_eval(
                extra_attributes["description"]
            )

        return template_config

    @property
    def get_function(self):
        return validate.create_function(self.code, self.function_entrypoint_name)

    def build(self):
        raise NotImplementedError
