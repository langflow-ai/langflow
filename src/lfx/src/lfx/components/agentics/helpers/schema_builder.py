"""Schema building utilities for Agentics components."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def build_schema_fields(fields: list[dict[str, Any]]) -> list[tuple[str, str, str, bool]]:
    """Convert field definitions to schema tuples for Pydantic model creation.

    Args:
        fields: List of field dictionaries with name, description, type, and multiple keys.

    Returns:
        List of tuples (name, description, type_str, required) for create_pydantic_model.
    """
    return [
        (
            field["name"],
            field["description"],
            field["type"] if not field["multiple"] else f"list[{field['type']}]",
            False,
        )
        for field in fields
    ]
