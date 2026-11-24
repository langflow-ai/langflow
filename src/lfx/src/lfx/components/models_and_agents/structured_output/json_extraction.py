"""Extract a JSON value embedded in arbitrary text. Used by the prompt-based fallback only."""

from __future__ import annotations

import json
from typing import Any

_DECODER = json.JSONDecoder()
_OPENERS = ("{", "[")


def extract_json_from_text(text: str) -> dict[str, Any] | list[Any] | None:
    """Return the first JSON object or array embedded in the text, or None when nothing parses.

    Walks the string looking for `{` or `[` and tries `JSONDecoder.raw_decode` at each
    candidate. Using `raw_decode` instead of a `.*`-greedy regex avoids spanning
    multiple JSON blobs as one string and naturally handles arrays as well as objects.
    """
    direct = _try_parse(text)
    if direct is not None:
        return direct

    for index in _candidate_indices(text):
        try:
            value, _ = _DECODER.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, (dict, list)):
            return value
    return None


def _candidate_indices(text: str) -> list[int]:
    return [i for i, ch in enumerate(text) if ch in _OPENERS]


def _try_parse(payload: str) -> dict[str, Any] | list[Any] | None:
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None
