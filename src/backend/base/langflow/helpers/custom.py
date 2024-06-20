from typing import Any, get_args


def format_type(type_: Any) -> str:
    if type_ == str:
        type_ = "Text"
    elif hasattr(type_, "__name__"):
        type_ = type_.__name__
    elif hasattr(type_, "__class__"):
        type_ = type_.__class__.__name__
    else:
        type_ = str(type_)
    return type_


def get_all_types_from_type(type_: Any) -> str:
    args = get_args(type_)
    if args:
        formatted_types = [format_type(arg) for arg in args]
        formatted_types.insert(0, format_type(type_))
        return formatted_types
    else:
        return [format_type(type_)]
