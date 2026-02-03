"""Formatting functions for Python code generation."""

from __future__ import annotations

from typing import Any

# Formatting thresholds
_MULTILINE_STRING_THRESHOLD = 80
_INLINE_LIST_ITEM_THRESHOLD = 60
_INLINE_DICT_MAX_ITEMS = 2
_INLINE_DICT_ITEM_THRESHOLD = 40


def format_value(value: Any, indent: int = 0) -> str:
    """Format a Python value for code generation.

    Handles strings, booleans, numbers, lists, and dicts with proper
    indentation and escaping.
    """
    if isinstance(value, str):
        return _format_string(value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return _format_list(value, indent)
    if isinstance(value, dict):
        return _format_dict(value, indent)
    return repr(value)


def _format_string(value: str) -> str:
    """Format a string value for Python code."""
    if value.startswith("$"):
        return value[1:]
    if "\n" in value or len(value) > _MULTILINE_STRING_THRESHOLD:
        escaped = value.replace('"""', r"\"\"\"")
        return f'"""{escaped}"""'
    return repr(value)


def _format_list(value: list, indent: int) -> str:
    """Format a list value for Python code."""
    if not value:
        return "[]"
    items = [format_value(v, indent + 4) for v in value]
    if len(items) == 1 and len(str(items[0])) < _INLINE_LIST_ITEM_THRESHOLD:
        return f"[{items[0]}]"
    inner = ",\n".join(" " * (indent + 4) + item for item in items)
    return f"[\n{inner},\n{' ' * indent}]"


def _format_dict(value: dict, indent: int) -> str:
    """Format a dict value for Python code."""
    if not value:
        return "{}"
    items = [f"{key!r}: {format_value(v, indent + 4)}" for key, v in value.items()]
    if len(items) <= _INLINE_DICT_MAX_ITEMS and all(len(i) < _INLINE_DICT_ITEM_THRESHOLD for i in items):
        return "{" + ", ".join(items) + "}"
    inner = ",\n".join(" " * (indent + 4) + item for item in items)
    return f"{{\n{inner},\n{' ' * indent}}}"
