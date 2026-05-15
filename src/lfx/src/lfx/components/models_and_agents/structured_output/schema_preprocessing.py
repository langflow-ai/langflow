"""Normalize Agent output_schema TableInput rows for build_model_from_schema."""

from __future__ import annotations

from typing import Any, TypedDict

_TRUTHY_MULTIPLE_STRINGS = frozenset({"true", "1", "t", "y", "yes"})


class NormalizedSchemaField(TypedDict):
    name: str
    type: str
    description: str
    multiple: bool


def preprocess_schema(schema: list[dict[str, Any]]) -> list[NormalizedSchemaField]:
    """Coerce raw TableInput rows into a typed schema accepted by build_model_from_schema."""
    return [_normalize_field(field) for field in schema]


def _normalize_field(field: dict[str, Any]) -> NormalizedSchemaField:
    return {
        "name": str(field.get("name", "field")),
        "type": str(field.get("type", "str")),
        "description": str(field.get("description", "")),
        "multiple": _coerce_multiple(field.get("multiple", False)),
    }


def _coerce_multiple(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in _TRUTHY_MULTIPLE_STRINGS
    return bool(value)
