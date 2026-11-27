"""The two limits every JSON value the engine reads must meet.

The Rust engine reads JSON text, and its parser refuses two things that
Python's ``json`` module accepts: a string that holds a lone surrogate, and
nesting deeper than 127 levels. The Python engine refuses the same values, so
both engines accept the same graphs (``limit_cases.json``). It checks the
operations it parses, the value it serializes and the handle strings it reads.
Apply and equality do not walk values, as they do not walk them for NaN: they
read graphs that were checked when they were written.
"""

from __future__ import annotations

import re
from typing import Any

from lfx.services.flow_operations.exceptions import FlowDataValidationError, FlowOperationValidationError

# The deepest nesting the engine reads. The outermost array or object is level 1.
MAX_DEPTH = 127
LONE_SURROGATE = "a string holds a lone surrogate"
TOO_DEEP = f"it nests deeper than {MAX_DEPTH} levels"

# Python reads a surrogate pair as one character, so any surrogate a string
# holds is a lone one.
_SURROGATE = re.compile("[\ud800-\udfff]")


def has_lone_surrogate(text: str) -> bool:
    """Return whether a string holds a lone surrogate."""
    return not text.isascii() and _SURROGATE.search(text) is not None


def broken_limit(value: Any) -> str | None:
    """Return the limit ``value`` breaks, or None when it breaks none."""
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, str):
            if has_lone_surrogate(item):
                return LONE_SURROGATE
        elif isinstance(item, (dict, list)):
            if depth > MAX_DEPTH:
                return TOO_DEEP
            if isinstance(item, dict):
                if any(isinstance(key, str) and has_lone_surrogate(key) for key in item):
                    return LONE_SURROGATE
                item = item.values()
            stack.extend((child, depth + 1) for child in item)
    return None


def graph_limit_error(limit: str) -> FlowDataValidationError:
    return FlowDataValidationError(f"flow data is not valid JSON: {limit}")


def check_graph_limits(value: Any) -> None:
    """Raise ``FlowDataValidationError`` when a graph or value breaks a limit."""
    limit = broken_limit(value)
    if limit is not None:
        raise graph_limit_error(limit)


def check_operation_limits(operations: Any) -> None:
    """Raise ``FlowOperationValidationError`` when raw operations break a limit."""
    limit = broken_limit(operations)
    if limit is not None:
        msg = f"operations are not valid JSON: {limit}"
        raise FlowOperationValidationError(msg)
