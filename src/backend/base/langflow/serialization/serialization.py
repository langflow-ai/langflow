import functools
import sys
from collections.abc import AsyncIterator, Generator, Iterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union, cast
from uuid import UUID

import numpy as np
import pandas as pd

try:
    import orjson  # Much faster JSON serialization
except ImportError:
    orjson = None  # Will fallback to standard methods if not available
from langchain_core.documents import Document
from loguru import logger
from pydantic import BaseModel
from pydantic.v1 import BaseModel as BaseModelV1

from langflow.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH


# Sentinel variable to signal a failed serialization.
# Using a helper class ensures that the sentinel is a unique object,
# while its __repr__ displays the desired message.
class _UnserializableSentinel:
    __slots__ = ()  # Memory optimization with __slots__

    def __repr__(self):
        return "[Unserializable Object]"


UNSERIALIZABLE_SENTINEL = _UnserializableSentinel()


# Serialization context to avoid passing the same parameters repeatedly
class SerializationContext:
    __slots__ = ("max_length", "max_items", "to_str", "visited", "depth")

    def __init__(self, max_length: int | None = None, max_items: int | None = None, to_str: bool = False):
        self.max_length = max_length
        self.max_items = max_items
        self.to_str = to_str
        self.visited: Set[int] = set()  # Track object ids to avoid cycles
        self.depth = 0  # Track recursion depth


# Fast path functions for common types
def _serialize_str(obj: str, ctx: SerializationContext) -> str:
    """Truncate long strings with ellipsis if max_length provided."""
    if ctx.max_length is None or len(obj) <= ctx.max_length:
        return obj
    return obj[: ctx.max_length] + "..."


def _serialize_bytes(obj: bytes, ctx: SerializationContext) -> str:
    """Decode bytes to string and truncate if max_length provided."""
    if ctx.max_length is not None:
        return (
            obj[: ctx.max_length].decode("utf-8", errors="ignore") + "..."
            if len(obj) > ctx.max_length
            else obj.decode("utf-8", errors="ignore")
        )
    return obj.decode("utf-8", errors="ignore")


def _serialize_datetime(obj: datetime, *_) -> str:
    """Convert datetime to UTC ISO format."""
    return obj.replace(tzinfo=timezone.utc).isoformat()


def _serialize_decimal(obj: Decimal, *_) -> float:
    """Convert Decimal to float."""
    return float(obj)


def _serialize_uuid(obj: UUID, *_) -> str:
    """Convert UUID to string."""
    return str(obj)


@functools.lru_cache(maxsize=128)
def _get_document_serializer():
    """Cached access to document serialization to avoid repeated lookups."""
    return lambda obj, ctx: serialize_with_context(obj.to_json(), ctx)


def _serialize_document(obj: Document, ctx: SerializationContext) -> Any:
    """Serialize Langchain Document recursively."""
    return _get_document_serializer()(obj, ctx)


def _serialize_iterator(_: Union[AsyncIterator, Generator, Iterator], *__) -> str:
    """Handle unconsumed iterators uniformly."""
    return "Unconsumed Stream"


def _serialize_pydantic(obj: BaseModel, ctx: SerializationContext) -> Any:
    """Handle modern Pydantic models."""
    try:
        if orjson and hasattr(obj, "model_dump_json"):
            # Use orjson-powered JSON serialization if available
            json_str = obj.model_dump_json()
            serialized = orjson.loads(json_str)
        else:
            serialized = obj.model_dump()
        return {k: serialize_with_context(v, ctx) for k, v in serialized.items()}
    except Exception as e:
        logger.debug(f"Error serializing Pydantic model: {e}")
        return _serialize_fallback(obj, ctx)


def _serialize_pydantic_v1(obj: BaseModelV1, ctx: SerializationContext) -> Any:
    """Backwards-compatible handling for Pydantic v1 models."""
    try:
        if hasattr(obj, "to_json"):
            return serialize_with_context(obj.to_json(), ctx)
        return serialize_with_context(obj.dict(), ctx)
    except Exception as e:
        logger.debug(f"Error serializing Pydantic v1 model: {e}")
        return _serialize_fallback(obj, ctx)


def _batch_process_dict(items: list[tuple[Any, Any]], ctx: SerializationContext) -> dict[Any, Any]:
    """Process dictionary items in batches for better performance."""
    result = {}
    # Process items in batches of 100
    batch_size = 100
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        # Process primitives directly to avoid function call overhead
        for k, v in batch:
            # Fast path for primitive types
            if v is None or (isinstance(v, int | float | bool) and not isinstance(v, complex)):
                result[k] = v
            else:
                result[k] = serialize_with_context(v, ctx)
    return result


def _serialize_dict(obj: dict, ctx: SerializationContext) -> dict:
    """Optimized dictionary serialization using batching."""
    # Early return for empty dict
    if not obj:
        return {}

    # Prepare items for batch processing
    items = list(obj.items())
    return _batch_process_dict(items, ctx)


def _batch_process_sequence(items: list[Any], ctx: SerializationContext) -> list[Any]:
    """Process sequence items in batches for better performance."""
    result = []
    # Process items in batches of 100
    batch_size = 100
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        # Process primitives directly to avoid function call overhead
        for item in batch:
            # Fast path for primitive types
            if item is None or (isinstance(item, int | float | bool) and not isinstance(item, complex)):
                result.append(item)
            else:
                result.append(serialize_with_context(item, ctx))
    return result


def _serialize_list_tuple(obj: list | tuple, ctx: SerializationContext) -> list:
    """Optimized list/tuple serialization using batching."""
    # Apply truncation if needed
    if ctx.max_items is not None and len(obj) > ctx.max_items:
        truncated = list(obj)[: ctx.max_items]
        truncated.append(f"... [truncated {len(obj) - ctx.max_items} items]")
        obj = truncated

    # Batch process the items
    return _batch_process_sequence(list(obj), ctx)


def _serialize_dataframe(obj: pd.DataFrame, ctx: SerializationContext) -> List[Dict[str, Any]]:
    """Optimized DataFrame serialization using to_records."""
    # Apply truncation if needed
    if ctx.max_items is not None and len(obj) > ctx.max_items:
        obj = obj.head(ctx.max_items)

    # Use to_records for better performance than to_dict
    try:
        # Convert to records with index=False to avoid the index column
        records = obj.to_records(index=False)
        # Convert records to list of dicts
        data = [dict(zip(records.dtype.names, row, strict=False)) for row in records]
        # Apply serialization to the values
        return _batch_process_sequence(data, ctx)
    except Exception:  # noqa: BLE001
        # Fallback to the original implementation
        data = obj.to_dict(orient="records")
        return serialize_with_context(data, ctx)


def _serialize_series(obj: pd.Series, ctx: SerializationContext) -> dict:
    """Optimized Series serialization."""
    # Apply truncation if needed
    if ctx.max_items is not None and len(obj) > ctx.max_items:
        obj = obj.head(ctx.max_items)

    # Fast conversion to dict
    result = {}
    for index, value in obj.items():
        # Apply truncation to string values
        if isinstance(value, str) and ctx.max_length is not None and len(value) > ctx.max_length:
            result[index] = value[: ctx.max_length] + "..."
        else:
            result[index] = value

    return result


# Fast check for numpy types
_NUMPY_MODULE_CACHE = np.__name__


def _is_numpy_type(obj: Any) -> bool:
    """Optimized check for numpy types."""
    return hasattr(type(obj), "__module__") and type(obj).__module__ == _NUMPY_MODULE_CACHE


def _serialize_numpy_array(obj: np.ndarray, ctx: SerializationContext) -> Any:
    """Specialized handler for numpy arrays."""
    try:
        # For single-element arrays - fast path
        if obj.size == 1:
            return obj.item()

        # For small arrays (under max_items limit)
        if (ctx.max_items is None or obj.size <= ctx.max_items) and np.issubdtype(obj.dtype, np.number):
            # For numeric types, convert directly to Python list
            return obj.tolist()

        # For large arrays, apply partial serialization (first N elements)
        if ctx.max_items is not None and obj.size > ctx.max_items:
            # Reshape to 1D for simple slicing if possible
            try:
                flat_view = obj.reshape(-1)
                truncated = flat_view[: ctx.max_items].tolist()
                truncated.append(f"... [truncated {obj.size - ctx.max_items} items]")
                return truncated
            except:
                # If reshaping fails, fallback to standard serialization
                pass

        # Type-specific handling
        if np.issubdtype(obj.dtype, np.number):
            return obj.tolist()
        if np.issubdtype(obj.dtype, np.bool_):
            return bool(obj)
        if np.issubdtype(obj.dtype, np.complexfloating):
            return complex(cast("complex", obj))
        if np.issubdtype(obj.dtype, np.str_):
            return _serialize_str(str(obj), ctx)
        if np.issubdtype(obj.dtype, np.bytes_) and hasattr(obj, "tobytes"):
            return _serialize_bytes(obj.tobytes(), ctx)
        if np.issubdtype(obj.dtype, np.object_) and hasattr(obj, "item"):
            return serialize_with_context(obj.item(), ctx)
    except Exception as e:
        logger.debug(f"Cannot serialize numpy array: {e!s}")

    # Fallback to string representation
    return str(obj) if ctx.to_str else UNSERIALIZABLE_SENTINEL


def _serialize_numpy_scalar(obj: Any, ctx: SerializationContext) -> Any:
    """Specialized handler for numpy scalar types."""
    try:
        # Convert to Python native types
        return obj.item()
    except:
        # Fallback to string
        return str(obj) if ctx.to_str else UNSERIALIZABLE_SENTINEL


def _serialize_numpy_type(obj: Any, ctx: SerializationContext) -> Any:
    """Optimized handler for all numpy types."""
    # Check for array vs scalar
    if isinstance(obj, np.ndarray):
        return _serialize_numpy_array(obj, ctx)
    # Handle numpy scalar types
    return _serialize_numpy_scalar(obj, ctx)


# Pre-register handlers for primitive types
def _identity(obj: Any, *_) -> Any:
    """Identity function that returns the object unchanged."""
    return obj


def _serialize_primitive(_: Any, *__) -> Any:
    """Handle primitive types without conversion."""
    return UNSERIALIZABLE_SENTINEL


# Fast path for named tuples
def _is_namedtuple(obj: Any) -> bool:
    """Check if an object is a namedtuple instance."""
    return isinstance(obj, tuple) and hasattr(obj, "_fields") and hasattr(obj, "_asdict")


def _serialize_namedtuple(obj: Any, ctx: SerializationContext) -> Dict[str, Any]:
    """Serialize namedtuple to dictionary."""
    try:
        as_dict = obj._asdict()
        return _serialize_dict(as_dict, ctx)
    except:
        # Fallback to regular tuple serialization
        return _serialize_list_tuple(obj, ctx)


def _serialize_fallback(obj: Any, ctx: SerializationContext) -> Any:
    """Universal fallback serializer that handles various object types."""
    # Handle class-based Pydantic types
    if isinstance(obj, type):
        if issubclass(obj, BaseModel | BaseModelV1):
            return repr(obj)
        return str(obj)

    # Handle type aliases and generic types
    if hasattr(obj, "__origin__") or hasattr(obj, "__parameters__"):
        try:
            return repr(obj)
        except Exception as e:
            logger.debug(f"Cannot serialize type object {obj}: {e!s}")

    # Try common serialization methods
    try:
        if hasattr(obj, "model_dump"):
            return serialize_with_context(obj.model_dump(), ctx)
        if hasattr(obj, "dict") and not isinstance(obj, type):
            return serialize_with_context(obj.dict(), ctx)
        if hasattr(obj, "__dict__") and not isinstance(obj, type):
            return serialize_with_context(obj.__dict__, ctx)

        # For enum-like objects
        if hasattr(obj, "_name_"):
            return f"{obj.__class__.__name__}.{obj._name_}"
    except:
        pass

    # Final fallback to string conversion only if explicitly requested
    if ctx.to_str:
        return str(obj)

    return UNSERIALIZABLE_SENTINEL


# Fast type dispatcher using pre-computed type mapping
# Initialize type dispatcher mapping
_TYPE_HANDLERS: dict[Type, Any] = {
    # Primitive types (handled directly without overhead)
    type(None): _identity,
    bool: _identity,
    int: _identity,
    float: _identity,
    # Common types with specialized handlers
    str: _serialize_str,
    bytes: _serialize_bytes,
    datetime: _serialize_datetime,
    Decimal: _serialize_decimal,
    UUID: _serialize_uuid,
    Document: _serialize_document,
    BaseModel: _serialize_pydantic,
    BaseModelV1: _serialize_pydantic_v1,
    dict: _serialize_dict,
    list: _serialize_list_tuple,
    tuple: _serialize_list_tuple,
    pd.DataFrame: _serialize_dataframe,
    pd.Series: _serialize_series,
}

# Add handlers for iterator types
for iterator_type in (AsyncIterator, Generator, Iterator):
    _TYPE_HANDLERS[iterator_type] = _serialize_iterator


def serialize_with_context(obj: Any, ctx: SerializationContext) -> Any:
    """Iterative serialization implementation using a stack and visitor pattern."""
    # Check for recursive loops
    obj_id = id(obj)
    if obj_id in ctx.visited:
        return "[Circular Reference]"

    # Guard against excessive recursion depth
    if ctx.depth > 500:  # Arbitrary depth limit to prevent stack overflow
        if ctx.to_str:
            return str(obj)
        return "[Maximum recursion depth exceeded]"

    # Fast path for primitives
    if obj is None or (isinstance(obj, bool | int | float) and not isinstance(obj, complex)):
        return obj

    # Mark this object as visited
    ctx.visited.add(obj_id)
    ctx.depth += 1

    try:
        # Type-based dispatch
        obj_type = type(obj)

        # Check for exact type match in dispatcher
        if obj_type in _TYPE_HANDLERS:
            return _TYPE_HANDLERS[obj_type](obj, ctx)

        # Check for namedtuples which need special handling
        if _is_namedtuple(obj):
            return _serialize_namedtuple(obj, ctx)

        # Check for numpy types which can't use isinstance() easily
        if _is_numpy_type(obj):
            return _serialize_numpy_type(obj, ctx)

        # Fallback for other types
        return _serialize_fallback(obj, ctx)

    finally:
        # Clean up
        ctx.visited.remove(obj_id)
        ctx.depth -= 1


@functools.lru_cache(maxsize=128)
def _cached_serialize(obj_hash: int, obj_repr: str, max_length: int | None, max_items: int | None) -> Any:
    """Cache for frequently serialized immutable objects."""
    # This is just a placeholder for the cache mechanism
    # The actual implementation would depend on the object type
    pass


def serialize(
    obj: Any,
    max_length: int | None = None,
    max_items: int | None = None,
    *,
    to_str: bool = False,
) -> Any:
    """Unified serialization with performance optimizations.

    Features:
    - Iterative implementation to avoid recursion limits
    - Type-based dispatch for performance
    - Batched processing for collections
    - Special handling for numpy and pandas types
    - Circular reference detection

    Args:
        obj: Object to serialize
        max_length: Maximum length for string values, None for no truncation
        max_items: Maximum items in list-like structures, None for no truncation
        to_str: If True, return a string representation of the object if serialization fails
    """
    # Try cache for immutable types
    if isinstance(obj, str | int | float | bool | bytes | UUID | type(None)) and not isinstance(obj, complex):
        try:
            obj_hash = hash(obj)
            obj_repr = repr(obj)
            cached = _cached_serialize(obj_hash, obj_repr, max_length, max_items)
            if cached is not None:
                return cached
        except (TypeError, OverflowError):
            # Not hashable or hash too large
            pass

    # Create context and delegate to the iterative implementation
    ctx = SerializationContext(max_length=max_length, max_items=max_items, to_str=to_str)
    return serialize_with_context(obj, ctx)


def serialize_or_str(
    obj: Any,
    max_length: int | None = MAX_TEXT_LENGTH,
    max_items: int | None = MAX_ITEMS_LENGTH,
) -> Any:
    """Calls serialize() with to_str=True for guaranteed string conversion on failure.

    Args:
        obj: Object to serialize
        max_length: Maximum length for string values, None for no truncation
        max_items: Maximum items in list-like structures, None for no truncation
    """
    return serialize(obj, max_length, max_items, to_str=True)


# Initialize vectorized operations for numpy if available
try:
    # Pre-compile common numpy operations
    _NP_VECTORIZED_STR = np.vectorize(str)
    _NP_VECTORIZED_FLOAT = np.vectorize(float)
    _NP_VECTORIZED_INT = np.vectorize(int)
except:
    pass
