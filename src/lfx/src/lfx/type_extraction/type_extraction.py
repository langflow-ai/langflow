import re
from collections.abc import Sequence as SequenceABC
from itertools import chain
from types import GenericAlias
from typing import Any, Union


def extract_inner_type_from_generic_alias(return_type: GenericAlias) -> Any:
    """Extracts the inner type from a type hint that is a list or a Optional."""
    if return_type.__origin__ in {list, SequenceABC}:
        return list(return_type.__args__)
    return return_type


def extract_inner_type(return_type: str) -> str:
    """Extracts the inner type from a type hint that is a list."""
    if match := re.match(r"list\[(.*)\]", return_type, re.IGNORECASE):
        return match[1]
    return return_type


def extract_union_types(return_type: str) -> list[str]:
    """Extracts the inner type from a type hint that is a list."""
    # If the return type is a Union, then we need to parse it
    return_type = return_type.replace("Union", "").replace("[", "").replace("]", "")
    return_types = return_type.split(",")
    return [item.strip() for item in return_types]


def extract_uniont_types_from_generic_alias(return_type: GenericAlias) -> list:
    """Extracts the inner type from a type hint that is a Union."""
    if isinstance(return_type, list):
        return [
            _inner_arg
            for _type in return_type
            for _inner_arg in _type.__args__
            if _inner_arg not in {Any, type(None), type(Any)}
        ]
    return list(return_type.__args__)


def post_process_type(type_):
    """Process the return type of a function.

    Args:
        type_ (Any): The return type of the function.

    Returns:
        Union[List[Any], Any]: The processed return type.
    """
    if hasattr(type_, "__origin__") and type_.__origin__ in {list, list, SequenceABC}:
        type_ = extract_inner_type_from_generic_alias(type_)

    # If the return type is not a Union, then we just return it as a list
    inner_type = type_[0] if isinstance(type_, list) else type_
    if (not hasattr(inner_type, "__origin__") or inner_type.__origin__ != Union) and (
        not hasattr(inner_type, "__class__") or inner_type.__class__.__name__ != "UnionType"
    ):
        return type_ if isinstance(type_, list) else [type_]
    # If the return type is a Union, then we need to parse it
    type_ = extract_union_types_from_generic_alias(type_)
    type_ = set(chain.from_iterable([post_process_type(t) for t in type_]))
    return list(type_)


def extract_union_types_from_generic_alias(return_type: GenericAlias) -> list:
    """Extracts the inner type from a type hint that is a Union."""
    if isinstance(return_type, list):
        return [
            _inner_arg
            for _type in return_type
            for _inner_arg in _type.__args__
            if _inner_arg not in {Any, type(None), type(Any)}
        ]
    return list(return_type.__args__)
