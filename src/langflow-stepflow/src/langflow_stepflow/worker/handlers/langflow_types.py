"""Handlers for Langflow core types (Message, Data, DataFrame).

Input: deserialize dicts with ``__langflow_type__`` markers back to lfx objects.
Output: serialize Message/Data objects to dicts with ``__langflow_type__`` markers.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import InputHandler, OutputHandler

logger = logging.getLogger(__name__)


def _is_langflow_type_dict(value: Any) -> bool:
    """Check if a single value is a dict with a ``__langflow_type__`` marker."""
    return isinstance(value, dict) and "__langflow_type__" in value


def _has_langflow_type_marker(value: Any) -> bool:
    """Check if a value (or list of values) contains __langflow_type__ markers."""
    if _is_langflow_type_dict(value):
        return True
    if isinstance(value, list):
        return any(_is_langflow_type_dict(item) for item in value)
    return False


def _deserialize_single(obj: dict[str, Any]) -> Any:
    """Deserialize a single dict with __langflow_type__ marker."""
    try:
        from lfx.schema.data import Data
        from lfx.schema.message import Message
    except ImportError:
        return obj

    langflow_type = obj.get("__langflow_type__")
    if not langflow_type:
        return obj

    obj_data = {k: v for k, v in obj.items() if k != "__langflow_type__"}

    if langflow_type == "Message":
        return Message(**obj_data)
    elif langflow_type == "Data":
        return Data(**obj_data)
    elif langflow_type == "DataFrame":
        return _deserialize_dataframe(obj_data, obj)

    return obj


def _deserialize_dataframe(obj_data: dict[str, Any], raw: dict[str, Any]) -> Any:
    """Deserialize a DataFrame from split JSON format with recovery fallback."""
    try:
        import io
        import json

        import pandas as pd
        from langflow.schema.dataframe import DataFrame

        text_key = obj_data.get("text_key", "text")
        default_value = obj_data.get("default_value", "")

        json_str = obj_data.get("json_data")
        if not json_str:
            raise ValueError("DataFrame missing required json_data field")

        json_io = io.StringIO(json_str if isinstance(json_str, str) else json.dumps(json_str))
        pd_df = pd.read_json(json_io, orient="split")
        data_list = pd_df.to_dict(orient="records")

        # Replace NaN with None for JSON compliance
        data_list = [{k: (None if pd.isna(v) else v) for k, v in record.items()} for record in data_list]

        return DataFrame(
            data=data_list,
            text_key=text_key,
            default_value=default_value,
        )
    except Exception:
        # Recovery fallback: try manual reconstruction
        return _recover_dataframe(raw)


def _recover_dataframe(raw_value: dict[str, Any]) -> Any:
    """Manual DataFrame recovery from split JSON format.

    Called when primary deserialization fails. Attempts a more lenient
    reconstruction from the raw serialized dict.
    """
    try:
        import io

        import pandas as pd
        from langflow.schema.dataframe import DataFrame as LfDataFrame

        json_str = raw_value.get("json_data")
        if not json_str or not isinstance(json_str, str):
            return raw_value

        pd_df = pd.read_json(io.StringIO(json_str), orient="split")
        records = pd_df.to_dict(orient="records")

        def clean_value(v: Any) -> Any:
            try:
                return None if pd.isna(v) else v
            except (ValueError, TypeError):
                return v

        data_list = [{k: clean_value(v) for k, v in record.items()} for record in records]

        return LfDataFrame(
            data=data_list,
            text_key=raw_value.get("text_key", "text"),
            default_value=raw_value.get("default_value", ""),
        )
    except Exception:
        return raw_value


class LangflowTypeInputHandler(InputHandler):
    """Deserialize dicts with ``__langflow_type__`` markers to lfx objects.

    Handles Message, Data, and DataFrame deserialization. Also handles
    list values containing marked dicts (recursive deserialization).
    Includes DataFrame recovery logic for robust handling of edge cases.
    """

    def matches(self, *, template_field: dict[str, Any], value: Any) -> bool:
        return _has_langflow_type_marker(value)

    async def prepare(self, fields: dict[str, tuple[Any, dict[str, Any]]], context: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, (value, _template_field) in fields.items():
            if _is_langflow_type_dict(value):
                result[key] = _deserialize_single(value)
            elif isinstance(value, list):
                result[key] = [_deserialize_single(item) if _is_langflow_type_dict(item) else item for item in value]

        return result


class LangflowTypeOutputHandler(OutputHandler):
    """Serialize Message and Data objects with ``__langflow_type__`` markers.

    Matches ``isinstance(value, (Message, Data))`` and produces dicts with
    ``model_dump(mode="json")`` plus a ``__langflow_type__`` key.
    """

    def matches(self, *, value: Any) -> bool:
        try:
            from lfx.schema.data import Data
            from lfx.schema.message import Message

            return isinstance(value, Message | Data)
        except ImportError:
            return False

    async def process(self, value: Any) -> Any:
        serialized = value.model_dump(mode="json")
        serialized["__langflow_type__"] = value.__class__.__name__
        return serialized
