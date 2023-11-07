import re


def extract_inner_type(return_type: str) -> str:
    """
    Extracts the inner type from a type hint that is a list.
    """
    if match := re.match(r"list\[(.*)\]", return_type, re.IGNORECASE):
        return match[1]
    return return_type


def extract_union_types(return_type: str) -> list[str]:
    """
    Extracts the inner type from a type hint that is a list.
    """
    # If the return type is a Union, then we need to parse it
    return_type = return_type.replace("Union", "").replace("[", "").replace("]", "")
    return_types = return_type.split(",")
    return_types = [item.strip() for item in return_types]
    return return_types
