"""Legacy prompt-based fallback for structured output: parse JSON from free text and validate."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from lfx.components.models_and_agents.structured_output.json_extraction import (
    extract_json_from_text,
)

_MISSING_SCHEMA_HINT = "Try setting an output schema"


def parse_and_validate_fallback_content(
    content: str,
    output_model: type[BaseModel] | None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Extract JSON from free text and validate it against output_model.

    Returns:
        - dict {"content", "error"} when no JSON could be extracted from content.
        - the raw parsed JSON dict when output_model is None.
        - a list[dict] of validated items when output_model is provided. Each failed
          item is replaced by {"data": ..., "validation_error": ...} so callers can
          surface partial validation problems without losing data.
    """
    parsed = extract_json_from_text(content)
    if parsed is None:
        return {"content": content, "error": _MISSING_SCHEMA_HINT}

    if output_model is None:
        if isinstance(parsed, dict):
            return parsed
        return parsed if isinstance(parsed, list) else {"content": content, "error": _MISSING_SCHEMA_HINT}

    if isinstance(parsed, list):
        return [_validate_item(item, output_model) for item in parsed]

    return [_validate_item(parsed, output_model)]


def _validate_item(item: Any, output_model: type[BaseModel]) -> dict[str, Any]:
    try:
        validated = output_model.model_validate(item)
    except ValidationError as exc:
        return {"data": item, "validation_error": str(exc)}
    return validated.model_dump()
