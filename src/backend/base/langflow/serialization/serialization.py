from collections.abc import AsyncIterator, Generator, Iterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from loguru import logger
from pydantic import BaseModel
from pydantic.v1 import BaseModel as BaseModelV1

from langflow.utils.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH


def _serialize_str(obj: str, max_length: int | None, _) -> str:
    """Truncate long strings with ellipsis if max_length provided."""
    if max_length is None:
        return obj
    return obj[:max_length] + "..." if len(obj) > max_length else obj


def _serialize_bytes(obj: bytes, max_length: int | None, _) -> str:
    """Decode bytes to string and truncate if max_length provided."""
    decoded = obj.decode("utf-8", errors="ignore")
    if max_length is None:
        return decoded
    return decoded[:max_length] + "..." if len(decoded) > max_length else decoded


def _serialize_datetime(obj: datetime, *_) -> str:
    """Convert datetime to UTC ISO format."""
    return obj.replace(tzinfo=timezone.utc).isoformat()


def _serialize_decimal(obj: Decimal, *_) -> float:
    """Convert Decimal to float."""
    return float(obj)


def _serialize_uuid(obj: UUID, *_) -> str:
    """Convert UUID to string."""
    return str(obj)


def _serialize_document(obj: Document, max_length: int | None, max_items: int | None) -> Any:
    """Serialize Langchain Document recursively."""
    return serialize(obj.to_json(), max_length, max_items)


def _serialize_iterator(_: AsyncIterator | Generator | Iterator, *__) -> str:
    """Handle unconsumed iterators uniformly."""
    return "Unconsumed Stream"


def _serialize_pydantic(obj: BaseModel, max_length: int | None, max_items: int | None) -> Any:
    """Handle modern Pydantic models."""
    serialized = obj.model_dump()
    return {k: serialize(v, max_length, max_items) for k, v in serialized.items()}


def _serialize_pydantic_v1(obj: BaseModelV1, max_length: int | None, max_items: int | None) -> Any:
    """Backwards-compatible handling for Pydantic v1 models."""
    if hasattr(obj, "to_json"):
        return serialize(obj.to_json(), max_length, max_items)
    return serialize(obj.dict(), max_length, max_items)


def _serialize_dict(obj: dict, max_length: int | None, max_items: int | None) -> dict:
    """Recursively process dictionary values."""
    return {k: serialize(v, max_length, max_items) for k, v in obj.items()}


def _serialize_list_tuple(obj: list | tuple, max_length: int | None, max_items: int | None) -> list:
    """Truncate long lists and process items recursively."""
    if max_items is not None and len(obj) > max_items:
        truncated = list(obj)[:max_items]
        truncated.append(f"... [truncated {len(obj) - max_items} items]")
        obj = truncated
    return [serialize(item, max_length, max_items) for item in obj]


def _serialize_primitive(obj: Any, *_) -> Any:
    """Handle primitive types without conversion."""
    if obj is None or isinstance(obj, int | float | bool):
        return obj
    return None


def _serialize_dispatcher(obj: Any, max_length: int | None, max_items: int | None) -> Any | None:
    """Dispatch object to appropriate serializer."""
    # Handle primitive types first
    if obj is None:
        return obj
    primitive = _serialize_primitive(obj, max_length, max_items)
    if primitive is not None:  # Special check for None since it's a valid primitive
        return primitive

    match obj:
        case str():
            return _serialize_str(obj, max_length, max_items)
        case bytes():
            return _serialize_bytes(obj, max_length, max_items)
        case datetime():
            return _serialize_datetime(obj, max_length, max_items)
        case Decimal():
            return _serialize_decimal(obj, max_length, max_items)
        case UUID():
            return _serialize_uuid(obj, max_length, max_items)
        case Document():
            return _serialize_document(obj, max_length, max_items)
        case AsyncIterator() | Generator() | Iterator():
            return _serialize_iterator(obj, max_length, max_items)
        case BaseModel():
            return _serialize_pydantic(obj, max_length, max_items)
        case BaseModelV1():
            return _serialize_pydantic_v1(obj, max_length, max_items)
        case dict():
            return _serialize_dict(obj, max_length, max_items)
        case list() | tuple():
            return _serialize_list_tuple(obj, max_length, max_items)
        case _:
            # Handle enums
            if hasattr(obj, "_name_"):  # Enum check
                return f"{obj.__class__.__name__}.{obj._name_}"
            # Handle TypeVars
            if hasattr(obj, "__name__") and hasattr(obj, "__bound__"):
                return repr(obj)
            # Handle type aliases and generic types
            if hasattr(obj, "__origin__") or hasattr(obj, "__parameters__"):
                return repr(obj)
            return None


def serialize(
    obj: Any,
    max_length: int | None = MAX_TEXT_LENGTH,
    max_items: int | None = MAX_ITEMS_LENGTH,
    *,
    to_str: bool = False,
) -> Any:
    """Unified serialization with optional truncation support.

    Coordinates specialized serializers through a dispatcher pattern.
    Maintains recursive processing for nested structures.

    Args:
        obj: Object to serialize
        max_length: Maximum length for string values, None for no truncation
        max_items: Maximum items in list-like structures, None for no truncation
        to_str: If True, return a string representation of the object if serialization fails
    """
    try:
        # First try type-specific serialization
        result = _serialize_dispatcher(obj, max_length, max_items)
        if result is not None or obj is None:  # Special check for None since it's a valid result
            return result

        # Handle class-based Pydantic types and other types
        if isinstance(obj, type):
            if issubclass(obj, BaseModel | BaseModelV1):
                return repr(obj)
            return str(obj)  # Handle other class types

        # Handle type aliases and generic types
        if hasattr(obj, "__origin__") or hasattr(obj, "__parameters__"):  # Type alias or generic type check
            try:
                return repr(obj)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Cannot serialize object {obj}: {e!s}")

        # Fallback to common serialization patterns
        if hasattr(obj, "model_dump"):
            return serialize(obj.model_dump(), max_length, max_items)
        if hasattr(obj, "dict") and not isinstance(obj, type):
            return serialize(obj.dict(), max_length, max_items)

        # Final fallback to string conversion
        if to_str or not isinstance(obj, type):  # Convert instances to string
            return str(obj)

    except Exception as e:  # noqa: BLE001
        logger.debug(f"Cannot serialize object {obj}: {e!s}")
        return "[Unserializable Object]"
    return obj


def serialize_or_str(
    obj: Any, max_length: int | None = MAX_TEXT_LENGTH, max_items: int | None = MAX_ITEMS_LENGTH
) -> Any:
    """Calls serialize() and if it fails, returns a string representation of the object.

    Args:
        obj: Object to serialize
        max_length: Maximum length for string values, None for no truncation
        max_items: Maximum items in list-like structures, None for no truncation
    """
    return serialize(obj, max_length, max_items, to_str=True)
