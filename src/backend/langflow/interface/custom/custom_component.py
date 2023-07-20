from typing import Callable, Optional
from fastapi import HTTPException
from langflow.interface.custom.constants import LANGCHAIN_BASE_TYPES
from langflow.interface.custom.component import Component

from langflow.utils import validate

from langflow.api.v1.endpoints import process_flow


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

        # TODO: Create the logic to validate what the Custom Component
        # should have as a prerequisite to be able to execute
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
    def get_main_class_name(self):
        tree = self.get_code_tree(self.code)

        base_name = self.code_class_base_inheritance
        method_name = self.function_entrypoint_name

        classes = []
        for item in tree.get("classes"):
            if base_name in item["bases"]:
                method_names = [method["name"] for method in item["methods"]]
                if method_name in method_names:
                    classes.append(item["name"])

        # Get just the first item
        return next(iter(classes), "")

    @property
    def build_template_config(self):
        tree = self.get_code_tree(self.code)

        attributes = [
            main_class["attributes"]
            for main_class in tree.get("classes")
            if main_class["name"] == self.get_main_class_name
        ]
        # Get just the first item
        attributes = next(iter(attributes), [])

        return super().build_template_config(attributes)

    @property
    def get_function(self):
        return validate.create_function(self.code, self.function_entrypoint_name)

    def load_flow(
        self, flow_id: str, inputs: Optional[dict] = None, tweaks: Optional[dict] = None
    ):
        return process_flow(flow_id, inputs, tweaks)

    def build(self):
        raise NotImplementedError
