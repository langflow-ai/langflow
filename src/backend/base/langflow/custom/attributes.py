import warnings
from typing import Callable

import emoji


def validate_icon(value: str, *args, **kwargs):
    # we are going to use the emoji library to validate the emoji
    # emojis can be defined using the :emoji_name: syntax

    if not value.startswith(":") and not value.endswith(":"):
        return value
    elif not value.startswith(":") or not value.endswith(":"):
        # emoji should have both starting and ending colons
        # so if one of them is missing, we will raise
        raise ValueError(f"Invalid emoji. {value} is not a valid emoji.")

    emoji_value = emoji.emojize(value, variant="emoji_type")
    if value == emoji_value:
        warnings.warn(f"Invalid emoji. {value} is not a valid emoji.")
        return value
    return emoji_value


def getattr_return_str(value):
    return str(value) if value else ""


def getattr_return_bool(value):
    if isinstance(value, bool):
        return value


def getattr_return_list_of_str(value):
    if isinstance(value, list):
        return [str(val) for val in value]
    return []


def getattr_return_list_of_object(value):
    if isinstance(value, list):
        return value
    return []


ATTR_FUNC_MAPPING: dict[str, Callable] = {
    "display_name": getattr_return_str,
    "description": getattr_return_str,
    "beta": getattr_return_bool,
    "documentation": getattr_return_str,
    "icon": validate_icon,
    "frozen": getattr_return_bool,
    "is_input": getattr_return_bool,
    "is_output": getattr_return_bool,
    "conditional_paths": getattr_return_list_of_str,
    "outputs": getattr_return_list_of_object,
    "inputs": getattr_return_list_of_object,
}
