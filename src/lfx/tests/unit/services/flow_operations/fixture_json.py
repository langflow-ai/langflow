"""Compact, deterministic JSON layout for the shared flow operation fixtures.

Two-space indentation, with any array or object that fits on one line kept
on one line, so the fixtures stay short enough to review.
"""

from __future__ import annotations

import json
from typing import Any

LINE_WIDTH = 160


def dumps(value: Any) -> str:
    """Return ``value`` as fixture JSON, ending with a newline."""
    return _dump(value, 0, 0) + "\n"


def _inline(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def _dump(value: Any, indent: int, used: int) -> str:
    inline = _inline(value)
    if not isinstance(value, (dict, list)) or not value or indent + used + len(inline) <= LINE_WIDTH:
        return inline
    pad = " " * (indent + 2)
    if isinstance(value, list):
        items = [pad + _dump(item, indent + 2, 0) for item in value]
        return "[\n" + ",\n".join(items) + "\n" + " " * indent + "]"
    items = []
    for key, item in value.items():
        prefix = json.dumps(key, ensure_ascii=False) + ": "
        items.append(pad + prefix + _dump(item, indent + 2, len(prefix)))
    return "{\n" + ",\n".join(items) + "\n" + " " * indent + "}"
