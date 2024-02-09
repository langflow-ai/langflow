import operator
import warnings
from typing import Any, ClassVar, Optional

import emoji
from cachetools import TTLCache, cachedmethod
from fastapi import HTTPException

from langflow.interface.custom.code_parser import CodeParser
from langflow.interface.custom.eval import eval_custom_component_code
from langflow.utils import validate


class ComponentCodeNullError(HTTPException):
    pass


class ComponentFunctionEntrypointNameNullError(HTTPException):
    pass


class Component:
    ERROR_CODE_NULL: ClassVar[str] = "Python code must be provided."
    ERROR_FUNCTION_ENTRYPOINT_NAME_NULL: ClassVar[str] = "The name of the entrypoint function must be provided."

    code: Optional[str] = None
    _function_entrypoint_name: str = "build"
    field_config: dict = {}
    _user_id: Optional[str]

    def __init__(self, **data):
        self.cache = TTLCache(maxsize=1024, ttl=60)
        for key, value in data.items():
            if key == "user_id":
                setattr(self, "_user_id", value)
            else:
                setattr(self, key, value)

        # Validate the emoji at the icon field
        if self.icon:
            self.icon = self.validate_icon(self.icon)

    def __setattr__(self, key, value):
        if key == "_user_id" and hasattr(self, "_user_id"):
            warnings.warn("user_id is immutable and cannot be changed.")
        super().__setattr__(key, value)

    @cachedmethod(cache=operator.attrgetter("cache"))
    def get_code_tree(self, code: str):
        parser = CodeParser(code)
        return parser.parse_code()

    def get_function(self):
        if not self.code:
            raise ComponentCodeNullError(
                status_code=400,
                detail={"error": self.ERROR_CODE_NULL, "traceback": ""},
            )

        if not self._function_entrypoint_name:
            raise ComponentFunctionEntrypointNameNullError(
                status_code=400,
                detail={
                    "error": self.ERROR_FUNCTION_ENTRYPOINT_NAME_NULL,
                    "traceback": "",
                },
            )

        return validate.create_function(self.code, self._function_entrypoint_name)

    def getattr_return_str(self, component, value):
        value = getattr(component, value)
        return str(value) if value else ""

    def build_template_config(self) -> dict:
        if not self.code:
            return {}

        cc_class = eval_custom_component_code(self.code)
        component_instance = cc_class()
        template_config = {}
        attributes_func_mapping = {
            "display_name": self.getattr_return_str,
            "description": self.getattr_return_str,
            "beta": self.getattr_return_str,
            "documentation": self.getattr_return_str,
            "icon": self.validate_icon,
        }

        for attribute, func in attributes_func_mapping.items():
            if hasattr(component_instance, attribute):
                template_config[attribute] = func(component=component_instance, value=attribute)

            return template_config

    def validate_icon(self, value: str, *args, **kwargs):
        # we are going to use the emoji library to validate the emoji
        # emojis can be defined using the :emoji_name: syntax
        if not value.startswith(":") or not value.endswith(":"):
            raise ValueError("Invalid emoji. Please use the :emoji_name: syntax.")

        emoji_value = emoji.emojize(value, variant="emoji_type")
        if value == emoji_value:
            raise ValueError(f"Invalid emoji. {value} is not a valid emoji.")
        return emoji_value

    def build(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
