from __future__ import annotations

import json
from typing import Any

from json_repair import repair_json


def validate_and_repair_json(json_str: str | dict) -> dict[str, Any] | str:
    """Validates a JSON string and attempts to repair it if invalid.

    Args:
        json_str (str): The JSON string to validate/repair

    Returns:
        Union[Dict[str, Any], str]: The parsed JSON dict if valid/repairable,
        otherwise returns the original string
    """
    if not isinstance(json_str, str):
        return json_str
    try:
        # Try normal JSON loads first (skip expensive repair if valid)
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    try:
        # Only repair *after* fast parse fails
        repaired = repair_json(json_str)
        return json.loads(repaired)
    except (json.JSONDecodeError, ImportError):
        # Return original if repair fails or module not found
        return json_str
