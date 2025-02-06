from collections.abc import AsyncIterator, Generator, Iterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import numpy as np
import pandas as pd
from langchain_core.documents import Document
from loguru import logger
from pydantic import BaseModel
from pydantic.v1 import BaseModel as BaseModelV1

from langflow.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH


# Sentinel variable to signal a failed serialization.
# Using a helper class ensures that the sentinel is a unique object,
# while its __repr__ displays the desired message.
class _UnserializableSentinel:
    def __repr__(self):
        return "[Unserializable Object]"


UNSERIALIZABLE_SENTINEL = _UnserializableSentinel()


def _serialize_str(obj: str, max_length: int | None, _) -> str:
    """Truncate long strings with ellipsis if max_length provided."""
    return obj if max_length is None or len(obj) <= max_length else obj[:max_length] + "..."


def _serialize_bytes(obj: bytes, max_length: int | None, _) -> str:
    """Decode bytes to string and truncate if max_length provided."""
    decoded = obj.decode("utf-8", errors="ignore")
    if max_length is None or len(decoded) <= max_length:
        return decoded
    return decoded[:max_length] + "..."


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
    return {k: serialize(v, max_length, max_items) for k, v in obj.model_dump().items()}


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
        return [serialize(item, max_length, max_items) for item in list(obj)[:max_items]] + [
            f"... [truncated {len(obj) - max_items} items]"
        ]
    return [serialize(item, max_length, max_items) for item in obj]


def _serialize_primitive(obj: Any, *_) -> Any:
    """Handle primitive types without conversion."""
    if obj is None or isinstance(obj, (int, float, bool, complex)):
        return obj
    return UNSERIALIZABLE_SENTINEL


def _serialize_instance(obj: Any, *_) -> str:
    """Handle regular class instances by converting to string."""
    return str(obj)


def _truncate_value(value: Any, max_length: int | None, max_items: int | None) -> Any:
    """Truncate value based on its type and provided limits."""
    if isinstance(value, str) and max_length is not None and len(value) > max_length:
        return value[:max_length]
    if isinstance(value, list | tuple) and max_items is not None and len(value) > max_items:
        return value[:max_items]
    return value


def _serialize_dataframe(obj: pd.DataFrame, max_length: int | None, max_items: int | None) -> list[dict]:
    """Serialize pandas DataFrame to a dictionary format."""
    if max_items is not None and len(obj) > max_items:
        obj = obj.head(max_items)
    return serialize(obj.to_dict(orient="records"), max_length, max_items)


def _serialize_series(obj: pd.Series, max_length: int | None, max_items: int | None) -> dict:
    """Serialize pandas Series to a dictionary format."""
    if max_items is not None and len(obj) > max_items:
        obj = obj.head(max_items)
    return {index: _truncate_value(value, max_length, max_items) for index, value in obj.items()}


def _is_numpy_type(obj: Any) -> bool:
    """Check if an object is a numpy type by checking its type's module name."""
    return hasattr(type(obj), "__module__") and type(obj).__module__ == np.__name__


def _serialize_numpy_type(obj: Any, max_length: int | None, max_items: int | None) -> Any:
    """Serialize numpy types."""
    if np.issubdtype(obj.dtype, np.number) and hasattr(obj, "item"):
        return obj.item()
    if np.issubdtype(obj.dtype, np.bool_):
        return bool(obj)
    if np.issubdtype(obj.dtype, np.complexfloating):
        return complex(cast(complex, obj))
    if np.issubdtype(obj.dtype, np.str_):
        return _serialize_str(str(obj), max_length, max_items)
    if np.issubdtype(obj.dtype, np.bytes_) and hasattr(obj, "tobytes"):
        return _serialize_bytes(obj.tobytes(), max_length, max_items)
    if np.issubdtype(obj.dtype, np.object_) and hasattr(obj, "item"):
        return _serialize_instance(obj.item(), max_length, max_items)
    return UNSERIALIZABLE_SENTINEL


def _serialize_dispatcher(obj: Any, max_length: int | None, max_items: int | None) -> Any | _UnserializableSentinel:
    """Dispatch object to appropriate serializer."""
    if obj is None:
        return obj
    primitive = _serialize_primitive(obj, max_length, max_items)
    if primitive is not UNSERIALIZABLE_SENTINEL:
        return primitive

    if isinstance(obj, str):
        return _serialize_str(obj, max_length, max_items)
    if isinstance(obj, bytes):
        return _serialize_bytes(obj, max_length, max_items)
    if isinstance(obj, datetime):
        return _serialize_datetime(obj, max_length, max_items)
    if isinstance(obj, Decimal):
        return _serialize_decimal(obj, max_length, max_items)
    if isinstance(obj, UUID):
        return _serialize_uuid(obj, max_length, max_items)
    if isinstance(obj, Document):
        return _serialize_document(obj, max_length, max_items)
    if isinstance(obj, (AsyncIterator, Generator, Iterator)):
        return _serialize_iterator(obj, max_length, max_items)
    if isinstance(obj, BaseModel):
        return _serialize_pydantic(obj, max_length, max_items)
    if isinstance(obj, BaseModelV1):
        return _serialize_pydantic_v1(obj, max_length, max_items)
    if isinstance(obj, dict):
        return _serialize_dict(obj, max_length, max_items)
    if isinstance(obj, pd.DataFrame):
        return _serialize_dataframe(obj, max_length, max_items)
    if isinstance(obj, pd.Series):
        return _serialize_series(obj, max_length, max_items)
    if isinstance(obj, (list, tuple)):
        return _serialize_list_tuple(obj, max_length, max_items)
    if _is_numpy_type(obj):
        return _serialize_numpy_type(obj, max_length, max_items)
    if not isinstance(obj, type):  # Match any instance that's not a class
        return _serialize_instance(obj, max_length, max_items)
    if hasattr(obj, "_name_"):  # Enum case
        return f"{obj.__class__.__name__}.{obj._name_}"
    if hasattr(obj, "__name__") and hasattr(obj, "__bound__"):  # TypeVar case
        return repr(obj)
    if hasattr(obj, "__origin__") or hasattr(obj, "__parameters__"):  # Type alias/generic case
        return repr(obj)
    return UNSERIALIZABLE_SENTINEL


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
    if obj is None:
        return None
    try:
        result = _serialize_dispatcher(obj, max_length, max_items)
        if result is not UNSERIALIZABLE_SENTINEL:
            return result

        if isinstance(obj, type):
            if issubclass(obj, (BaseModel, BaseModelV1)):
                return repr(obj)
            return str(obj)

        # Handle type aliases and generic types
        if hasattr(obj, "__origin__") or hasattr(obj, "__parameters__"):
            return repr(obj)

        if hasattr(obj, "model_dump"):
            return serialize(obj.model_dump(), max_length, max_items)
        if hasattr(obj, "dict") and not isinstance(obj, type):
            return serialize(obj.dict(), max_length, max_items)

        # Final fallback to string conversion only if explicitly requested
        if to_str:
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
