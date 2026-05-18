"""Handlers for Pydantic BaseModel serialization and deserialization.

Input: reconstruct BaseModel instances from dicts with ``__class_name__`` markers.
Output: serialize BaseModel instances with class metadata and SecretStr handling.
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


def _looks_like_env_var_name(value: str) -> bool:
    """Check if a string looks like an environment variable name.

    Matches strings that are all uppercase letters/digits/underscores and
    contain at least one underscore, like ``OPENAI_API_KEY`` or
    ``AWS_SECRET_KEY``. The underscore requirement avoids matching short
    names like ``PATH`` or ``HOME``.
    """
    return value.isupper() and "_" in value


def _resolve_secret_value(secret_value: Any) -> Any:
    """Resolve a SecretStr value, attempting env var lookup if it looks like one.

    Only attempts resolution when the value looks like an env var name
    (all uppercase with underscores) to avoid accidentally matching
    unrelated environment variables.
    """
    if not isinstance(secret_value, str) or not secret_value:
        return secret_value

    if not _looks_like_env_var_name(secret_value):
        return secret_value

    import os

    resolved = os.getenv(secret_value)
    return resolved if resolved is not None else secret_value


def _handle_special_pydantic_types(obj: Any, serialized: dict[str, Any]) -> dict[str, Any]:
    """Handle SecretStr and other special Pydantic types during serialization."""
    try:
        if hasattr(obj, "model_fields"):
            fields = obj.model_fields
            for field_name, field_info in fields.items():
                if hasattr(field_info, "annotation"):
                    field_type = field_info.annotation
                    if _is_secret_str_type(field_type):
                        field_value = getattr(obj, field_name, None)
                        if field_value is not None:
                            try:
                                secret_value = field_value.get_secret_value()
                                serialized[field_name] = _resolve_secret_value(secret_value)
                            except Exception:
                                pass
        elif hasattr(obj, "__fields__"):
            fields = obj.__fields__
            for field_name, field_info in fields.items():
                field_type = field_info.type_
                if _is_secret_str_type(field_type):
                    field_value = getattr(obj, field_name, None)
                    if field_value is not None:
                        try:
                            secret_value = field_value.get_secret_value()
                            serialized[field_name] = _resolve_secret_value(secret_value)
                        except Exception:
                            pass
    except Exception:
        pass

    return serialized


class BaseModelOutputHandler(OutputHandler):
    """Serialize Pydantic BaseModel instances with class metadata.

    Produces dicts with ``__class_name__`` and ``__module_name__`` markers.
    Includes special handling for SecretStr fields (resolves env vars).
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

        serialized = _handle_special_pydantic_types(value, serialized)

        serialized["__class_name__"] = value.__class__.__name__
        serialized["__module_name__"] = value.__class__.__module__
        return serialized
