import warnings

import emoji


def validate_icon(value: str, *args, **kwargs):
    # we are going to use the emoji library to validate the emoji
    # emojis can be defined using the :emoji_name: syntax
    if not value.startswith(":") or not value.endswith(":"):
        warnings.warn("Invalid emoji. Please use the :emoji_name: syntax.")
        return value
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


ATTR_FUNC_MAPPING = {
    "display_name": getattr_return_str,
    "description": getattr_return_str,
    "beta": getattr_return_str,
    "documentation": getattr_return_str,
    "icon": validate_icon,
    "pinned": getattr_return_bool,
}
