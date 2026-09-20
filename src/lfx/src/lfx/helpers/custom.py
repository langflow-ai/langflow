from typing import Any, TypeVar, get_origin

_TYPE_VAR_RUNTIME_TYPE = type(TypeVar("_T"))


def format_type(type_: Any) -> str:
    if type_ is str:
        type_ = "Text"
    elif issubclass(type(type_), type):
        type_ = type.__getattribute__(type_, "__name__")
    elif type(type_) is _TYPE_VAR_RUNTIME_TYPE:
        type_ = _TYPE_VAR_RUNTIME_TYPE.__getattribute__(type_, "__name__")
    elif (origin := get_origin(type_)) is not None and isinstance(origin, type):
        type_ = type.__getattribute__(origin, "__name__")
    else:
        type_ = type.__getattribute__(type(type_), "__name__")
    return type_
