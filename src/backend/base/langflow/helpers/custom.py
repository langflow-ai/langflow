from typing import Any


def format_type(type_: Any) -> str:
    """Formats the type into a string representation suitable for frontend or documentation.

    Special handling:
    - If the type is a list of some type (e.g., list[Data] or typing.List[Data]), returns 'list[InnerType]'.
    - If the type is str, returns 'Text'.
    - Otherwise, returns the type's name or string representation.

    Args:
        type_ (Any): The type to format.

    Returns:
        str: The formatted type as a string.
    """
    # Handle typing generics (Python 3.9+ and typing.List)
    origin = getattr(type_, "__origin__", None)
    args = getattr(type_, "__args__", ())

    # Check for list[InnerType] or typing.List[InnerType]
    if origin in (list,):
        if args:
            inner_type = args[0]
            if hasattr(inner_type, "__name__"):
                inner_type_name = inner_type.__name__
            elif hasattr(inner_type, "__class__"):
                inner_type_name = inner_type.__class__.__name__
            else:
                inner_type_name = str(inner_type)
            return f"List[{inner_type_name}]"
        return "List[Any]"

    # Handle direct type comparison for str
    if type_ is str:
        return "Text"

    # Fallbacks for other types
    if hasattr(type_, "__name__"):
        return type_.__name__
    if hasattr(type_, "__class__"):
        return type_.__class__.__name__
    return str(type_)
