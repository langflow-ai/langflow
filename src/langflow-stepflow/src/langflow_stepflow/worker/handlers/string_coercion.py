"""Input handler that coerces Langflow Message objects to plain strings."""

from __future__ import annotations

from typing import Any

from .base import InputHandler


class StringCoercionInputHandler(InputHandler):
    """Coerce Langflow Message objects to their ``.text`` for string fields.

    Matches template fields with ``type == "str"`` whose runtime value is a
    Langflow ``Message`` instance. Extracts the ``text`` attribute so the
    component receives a plain string as expected.

    This is needed because lfx components (1.6.4+) are stricter about type
    validation and reject Message objects for string-typed inputs.
    """

    def matches(self, *, template_field: dict[str, Any], value: Any) -> bool:
        if template_field.get("type") != "str":
            return False
        return (
            hasattr(value, "__class__")
            and value.__class__.__name__ == "Message"
            and hasattr(value, "text")
        )

    async def prepare(
        self, fields: dict[str, tuple[Any, dict[str, Any]]], context: Any
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, (value, _template_field) in fields.items():
            if (
                hasattr(value, "__class__")
                and value.__class__.__name__ == "Message"
                and hasattr(value, "text")
            ):
                result[key] = value.text

        return result
