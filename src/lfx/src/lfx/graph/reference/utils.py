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
        The value at the path, or None if not found
    """
    if data is None:
        return None

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
            return None

        # Check if this is an array index
        index_match = ARRAY_INDEX_PATTERN.match(segment)
        if index_match:
            index = int(index_match.group(1))
            if isinstance(result, (list, tuple)) and 0 <= index < len(result):
                result = result[index]
            else:
                return None
        elif isinstance(result, dict):
            result = result.get(segment)
        else:
            # Reject private/dunder attributes for security
            if segment.startswith("_"):
                return None
            # Try attribute access as fallback
            result = getattr(result, segment, None)

    return result
