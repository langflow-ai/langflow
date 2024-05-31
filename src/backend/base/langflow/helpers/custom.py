from typing import Any


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
