import ast
import operator
import warnings
from typing import Any, ClassVar, Optional

from cachetools import TTLCache, cachedmethod
from fastapi import HTTPException
from langflow.interface.custom.code_parser import CodeParser
from langflow.template.category.categories import Category
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

    def build_template_config(self, attributes) -> dict:
        template_config = {}

        for item in attributes:
            item_name = item.get("name")

            if item_value := item.get("value"):
                if "display_name" in item_name:
                    template_config["display_name"] = ast.literal_eval(item_value)

                elif "description" in item_name:
                    template_config["description"] = ast.literal_eval(item_value)

                elif "beta" in item_name:
                    template_config["beta"] = ast.literal_eval(item_value)

                elif "documentation" in item_name:
                    template_config["documentation"] = ast.literal_eval(item_value)

                elif "categories" in item_name:
                    categories_list = ast.literal_eval(item_value)
                    categories_list = self.validate_categories(categories_list)
                    template_config["categories"] = categories_list

                elif "tags" in item_name:
                    tags_list = ast.literal_eval(item_value)
                    tags_list = self.validate_tags(tags_list)
                    template_config["tags"] = tags_list

        return template_config

    def validate_categories(self, categories: list[str]) -> list[str]:
        for category in categories:
            if category not in Category:
                raise ValueError(f"Category {category} not found.")
        return categories

    def validate_tags(self, tags: list[str]) -> list[str]:
        return tags

    def build(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
