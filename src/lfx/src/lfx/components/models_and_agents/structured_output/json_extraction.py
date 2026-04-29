"""Extract a JSON value embedded in arbitrary text. Used by the prompt-based fallback only."""

from __future__ import annotations

import json
import re
from typing import Any

_EMBEDDED_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_from_text(text: str) -> dict[str, Any] | list[Any] | None:
    """Return the first JSON object or array found in the text, or None when nothing parses."""
    direct = _try_parse(text)
    if direct is not None:
        return direct

    match = _EMBEDDED_OBJECT_PATTERN.search(text)
    if match is None:
        return None
    return _try_parse(match.group())


def _try_parse(payload: str) -> dict[str, Any] | list[Any] | None:
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None
