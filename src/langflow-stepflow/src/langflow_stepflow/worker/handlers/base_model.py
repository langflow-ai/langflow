"""Handlers for Pydantic BaseModel serialization and deserialization.

Input: reconstruct BaseModel instances from dicts with ``__class_name__`` markers.
Output: serialize BaseModel instances with class metadata. ``SecretStr`` fields are left
masked by Pydantic's ``model_dump`` -- secrets are never unwrapped onto this serialized
output edge (the orchestrator routes it between steps and may stream it back).
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from .base import InputHandler, OutputHandler

logger = logging.getLogger(__name__)


def _has_class_name_marker(value: Any) -> bool:
    """Check if a value (or list of values) contains __class_name__ markers."""
    if isinstance(value, dict) and "__class_name__" in value:
        return True
    if isinstance(value, list):
        return any(isinstance(item, dict) and "__class_name__" in item for item in value)
    return False


def _deserialize_base_model(obj: dict[str, Any]) -> Any:
    """Deserialize a dict with __class_name__ marker back to a BaseModel instance."""
    class_name = obj.get("__class_name__")
    module_name = obj.get("__module_name__")
    if not class_name or not module_name:
        return obj

    try:
        module = importlib.import_module(module_name)
        class_type = getattr(module, class_name)

        obj_data = {k: v for k, v in obj.items() if k not in ("__class_name__", "__module_name__")}

        return class_type(**obj_data)
    except Exception:
        logger.debug("Failed to reconstruct BaseModel %s.%s", module_name, class_name)
        return obj


class BaseModelInputHandler(InputHandler):
    """Deserialize dicts with ``__class_name__`` markers to BaseModel instances.

    Handles dynamic import and reconstruction of arbitrary Pydantic models.
    Also handles list values containing marked dicts.
    """

    def matches(self, *, template_field: dict[str, Any], value: Any) -> bool:
        return _has_class_name_marker(value)

    async def prepare(self, fields: dict[str, tuple[Any, dict[str, Any]]], context: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, (value, _template_field) in fields.items():
            if isinstance(value, dict) and "__class_name__" in value:
                result[key] = _deserialize_base_model(value)
            elif isinstance(value, list):
                result[key] = [
                    _deserialize_base_model(item) if isinstance(item, dict) and "__class_name__" in item else item
                    for item in value
                ]

        return result


def _is_secret_str_type(field_type: Any) -> bool:
    """Check if a field type is SecretStr or similar secret type."""
    try:
        if hasattr(field_type, "__origin__"):
            if field_type.__origin__ is type(None) or str(field_type.__origin__) == "typing.Union":
                if hasattr(field_type, "__args__"):
                    for arg in field_type.__args__:
                        if _is_secret_str_type(arg):
                            return True

        type_name = getattr(field_type, "__name__", str(field_type))
        return "SecretStr" in type_name or "Secret" in type_name
    except Exception:
        return False


class BaseModelOutputHandler(OutputHandler):
    """Serialize Pydantic BaseModel instances with class metadata.

    Produces dicts with ``__class_name__`` and ``__module_name__`` markers. ``SecretStr``
    fields stay masked: ``model_dump(mode="json")`` renders them as ``'**********'`` and we
    never unwrap them onto the serialized output. If a downstream component needs the real
    value, it must be resolved on that component's input/config edge inside the worker, not
    carried through the orchestrator (see follow-up for real component execution).
    """

    def matches(self, *, value: Any) -> bool:
        try:
            from pydantic import BaseModel

            if not isinstance(value, BaseModel):
                return False

            # Don't match Langflow types (handled by LangflowTypeOutputHandler)
            try:
                from lfx.schema.data import Data
                from lfx.schema.dataframe import DataFrame
                from lfx.schema.message import Message

                if isinstance(value, Message | Data | DataFrame):
                    return False
            except ImportError:
                pass

            return True
        except ImportError:
            return False

    async def process(self, value: Any) -> Any:
        try:
            serialized = value.model_dump(mode="json", warnings=False)
        except Exception:
            serialized = value.model_dump(mode="json")

        serialized["__class_name__"] = value.__class__.__name__
        serialized["__module_name__"] = value.__class__.__module__
        return serialized
