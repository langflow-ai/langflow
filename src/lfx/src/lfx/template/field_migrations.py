"""Explicit migrations for saved component fields whose editor type changed."""

from collections.abc import Mapping
from typing import Any


def can_migrate_chat_output_input(
    component_class_name: str | None,
    field_name: str,
    current_field: Mapping[str, Any],
    saved_field: Mapping[str, Any],
) -> bool:
    """Preserve ChatOutput's historical string input when it becomes a HandleInput.

    Both versions accept messages and strings. This is not a general str/other type alias.
    MessageInput also converted serialized message objects, which HandleInput does not do.
    Only strings (or an unset value) can be copied unchanged. Connection types are checked
    separately. Keep this rule in sync with the frontend's chat-output-migration.ts.
    """
    return (
        component_class_name == "ChatOutput"
        and field_name == "input_value"
        and saved_field.get("type") == "str"
        and current_field.get("type") == "other"
        and current_field.get("_input_type") == "HandleInput"
        and (saved_field.get("value") is None or isinstance(saved_field.get("value"), str))
    )


def migrate_mrscraper_html_field(
    field_name: str, current_field: Mapping[str, Any], saved_field: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Convert literal values that changed type in the MrScraper HTML template."""
    if current_field.get("type") != "str" or saved_field.get("load_from_db") or saved_field.get("file_path"):
        return None

    value = saved_field.get("value")
    if field_name == "max_retries" and saved_field.get("type") == "int" and type(value) is int:
        return {**saved_field, "type": "str", "value": str(value)}
    if field_name == "screenshot" and saved_field.get("type") == "bool" and isinstance(value, bool):
        return {**saved_field, "type": "str", "value": "full" if value else "None"}
    return None
