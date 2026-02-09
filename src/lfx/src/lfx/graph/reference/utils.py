# src/lfx/src/lfx/graph/reference/utils.py
import re
from typing import Any

# Pattern to match array indices like [0], [123]
ARRAY_INDEX_PATTERN = re.compile(r"\[(\d+)\]")


def traverse_dot_path(data: Any, path: str) -> Any:
    """Traverse a nested data structure using dot notation.

    Supports:
    - Dot notation: "user.name"
    - Array indices: "items[0]"
    - Combined: "users[0].name"

    Args:
        data: The data structure to traverse
        path: Dot-separated path with optional array indices

    Returns:
        The value at the path

    Raises:
        ValueError: If the path cannot be traversed (missing key, index out of range, etc.)
    """
    if data is None:
        msg = f"Cannot traverse path '{path}' on None value"
        raise ValueError(msg)

    if not path:
        return data

    # Split path into segments, handling array indices
    # "users[0].name" -> ["users", "[0]", "name"]
    segments = []
    current = ""

    for char in path:
        if char == ".":
            if current:
                segments.append(current)
                current = ""
        elif char == "[":
            if current:
                segments.append(current)
                current = ""
            current = "["
        elif char == "]":
            current += "]"
            segments.append(current)
            current = ""
        else:
            current += char

    if current:
        segments.append(current)

    # Traverse the path
    result = data
    for segment in segments:
        if result is None:
            msg = f"Cannot traverse '{segment}' on None value (remaining path: '{path}')"
            raise ValueError(msg)

        # Check if this is an array index
        index_match = ARRAY_INDEX_PATTERN.match(segment)
        if index_match:
            index = int(index_match.group(1))
            if isinstance(result, (list, tuple)) and 0 <= index < len(result):
                result = result[index]
            else:
                length = len(result) if isinstance(result, (list, tuple)) else "N/A"
                msg = f"Index {index} out of range for {type(result).__name__} (length {length}) at path '{path}'"
                raise ValueError(msg)
        elif isinstance(result, dict):
            if segment not in result:
                msg = f"Key '{segment}' not found in dict (available keys: {list(result.keys())}) at path '{path}'"
                raise ValueError(msg)
            result = result[segment]
        else:
            # Reject private/dunder attributes for security
            if segment.startswith("_"):
                msg = f"Access to private attribute '{segment}' is not allowed at path '{path}'"
                raise ValueError(msg)
            # Try attribute access as fallback
            if not hasattr(result, segment):
                msg = f"Attribute '{segment}' not found on {type(result).__name__} at path '{path}'"
                raise ValueError(msg)
            result = getattr(result, segment)

    return result
