import copy
import operator
import re
from typing import TYPE_CHECKING, Any, ClassVar

from cachetools import TTLCache, cachedmethod
from fastapi import HTTPException
from loguru import logger

from lfx.custom.attributes import ATTR_FUNC_MAPPING
from lfx.custom.code_parser.code_parser import CodeParser
from lfx.custom.eval import eval_custom_component_code
from lfx.utils.util import validate

if TYPE_CHECKING:
    from uuid import UUID


class ComponentCodeNullError(HTTPException):
    pass


class ComponentFunctionEntrypointNameNullError(HTTPException):
    pass


class BaseComponent:
    ERROR_CODE_NULL: ClassVar[str] = "Python code must be provided."
    ERROR_FUNCTION_ENTRYPOINT_NAME_NULL: ClassVar[str] = "The name of the entrypoint function must be provided."

    def __init__(self, **data) -> None:
        self._code: str | None = None
        self._function_entrypoint_name: str = "build"
        self.field_config: dict = {}
        self._user_id: str | UUID | None = None
        self._template_config: dict = {}

        self.cache: TTLCache = TTLCache(maxsize=1024, ttl=60)

        for key, value in data.items():
            if key == "user_id":
                self._user_id = value
            else:
                setattr(self, key, value)

    def __setattr__(self, key, value) -> None:
        if key == "_user_id":
            try:
                if self._user_id is not None:
                    logger.warning("user_id is immutable and cannot be changed.")
            except (KeyError, AttributeError):
                pass
        super().__setattr__(key, value)

    @cachedmethod(cache=operator.attrgetter("cache"))
    def get_code_tree(self, code: str):
        parser = CodeParser(code)
        return parser.parse_code()

    def get_function(self):
        if not self._code:
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

        return validate.create_function(self._code, self._function_entrypoint_name)

    @staticmethod
    def get_template_config(component):
        """Gets the template configuration for the custom component itself."""
        template_config = {}

        for attribute, func in ATTR_FUNC_MAPPING.items():
            if hasattr(component, attribute):
                value = getattr(component, attribute)
                if value is not None:
                    value_copy = copy.deepcopy(value)
                    template_config[attribute] = func(value=value_copy)

        for key in template_config.copy():
            if key not in ATTR_FUNC_MAPPING:
                template_config.pop(key, None)

        return template_config

    def build_template_config(self) -> dict:
        """Builds the template configuration for the custom component.

        Returns:
            A dictionary representing the template configuration.
        """
        if not self._code:
            return {}

        try:
            cc_class = eval_custom_component_code(self._code)

        except AttributeError as e:
            pattern = r"module '.*?' has no attribute '.*?'"
            if re.search(pattern, str(e)):
                raise ImportError(e) from e
            raise

        component_instance = cc_class(_code=self._code)
        return self.get_template_config(component_instance)

    def build(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
