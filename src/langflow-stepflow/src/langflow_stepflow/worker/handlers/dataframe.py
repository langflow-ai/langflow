"""Handlers for DataFrame conversion (input) and serialization (output)."""

from __future__ import annotations

import logging
from typing import Any

from .base import InputHandler, OutputHandler

logger = logging.getLogger(__name__)


def _is_data_list(value: list[Any]) -> bool:
    """Check if a list contains Data-like objects suitable for DataFrame conversion."""
    non_null = [item for item in value if item is not None]
    if not non_null:
        return False
    return all(
        (isinstance(item, dict) and ("text" in item or "__class_name__" in item))
        or (hasattr(item, "__class__") and item.__class__.__name__ == "Data")
        for item in non_null
    )


class DataFrameConversionInputHandler(InputHandler):
    """Convert lists of Data objects to DataFrames for DataFrame-typed fields.

    Matches template fields whose ``input_types`` include ``"DataFrame"``
    and whose runtime value is a non-empty list of Data-like objects.
    """

    def matches(self, *, template_field: dict[str, Any], value: Any) -> bool:
        if "DataFrame" not in template_field.get("input_types", []):
            return False
        return isinstance(value, list) and len(value) > 0

    async def prepare(
        self, fields: dict[str, tuple[Any, dict[str, Any]]], context: Any
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, (value, _template_field) in fields.items():
            if not isinstance(value, list) or not value:
                continue

            if not _is_data_list(value):
                continue

            try:
                from langflow.schema.dataframe import DataFrame

                result[key] = DataFrame(data=value)
            except Exception:
                logger.debug("DataFrame conversion failed for field %r", key)

        return result


class DataFrameOutputHandler(OutputHandler):
    """Serialize DataFrame objects to split JSON format.

    Uses ``orient="split"`` for ~45% size reduction compared to records format.
    """

    def matches(self, *, value: Any) -> bool:
        try:
            import pandas as pd

            return isinstance(value, pd.DataFrame)
        except ImportError:
            return False

    async def process(self, value: Any) -> Any:
        json_str = value.to_json(orient="split")
        return {
            "__langflow_type__": "DataFrame",
            "json_data": json_str,
            "text_key": getattr(value, "text_key", "text"),
            "default_value": getattr(value, "default_value", ""),
        }
