import re


def extract_inner_type(return_type: str) -> str:
    """
    Extracts the inner type from a type hint that is a list.
    """
    if match := re.match(r"list\[(.*)\]", return_type, re.IGNORECASE):
        return match[1]
    return return_type
