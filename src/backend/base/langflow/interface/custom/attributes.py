from typing import Callable

from langflow.utils.util import validate_icon


def getattr_return_str(value):
    return str(value) if value else ""


def getattr_return_bool(value):
    if isinstance(value, bool):
        return value


ATTR_FUNC_MAPPING: dict[str, Callable] = {
    "display_name": getattr_return_str,
    "description": getattr_return_str,
    "beta": getattr_return_bool,
    "documentation": getattr_return_str,
    "icon": validate_icon,
    "frozen": getattr_return_bool,
    "is_input": getattr_return_bool,
    "is_output": getattr_return_bool,
}
