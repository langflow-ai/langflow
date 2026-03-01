from datetime import datetime, timezone
from uuid import UUID

from pydantic import BeforeValidator

_CACHE_MAXSIZE = 4096

_SENTINEL = object()

# Small module-level cache to avoid repeated str(UUID) calls for the same hashable inputs.
_CACHE: dict[object, str | None] = {}


def timestamp_to_str(timestamp: datetime | str) -> str:
    """Convert timestamp to standardized string format.

    Handles multiple input formats and ensures consistent UTC timezone output.

    Args:
        timestamp (datetime | str): Input timestamp either as datetime object or string

    Returns:
        str: Formatted timestamp string in 'YYYY-MM-DD HH:MM:SS UTC' format

    Raises:
        ValueError: If string timestamp is in invalid format
    """
    if isinstance(timestamp, str):
        # Try parsing with different formats
        formats = [
            "%Y-%m-%dT%H:%M:%S",  # ISO format
            "%Y-%m-%d %H:%M:%S %Z",  # Standard with timezone
            "%Y-%m-%d %H:%M:%S",  # Without timezone
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
            "%Y-%m-%dT%H:%M:%S%z",  # ISO with numeric timezone
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt).replace(tzinfo=timezone.utc)
                return parsed.strftime("%Y-%m-%d %H:%M:%S %Z")
            except ValueError:
                continue

        msg = f"Invalid timestamp format: {timestamp}"
        raise ValueError(msg)

    # Handle datetime object
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")


def str_to_timestamp(timestamp: str | datetime) -> datetime:
    """Convert timestamp to datetime object.

    Handles multiple input formats and ensures consistent UTC timezone output.

    Args:
        timestamp (str | datetime): Input timestamp either as string or datetime object

    Returns:
        datetime: Datetime object with UTC timezone

    Raises:
        ValueError: If string timestamp is not in 'YYYY-MM-DD HH:MM:SS UTC' format
    """
    if isinstance(timestamp, str):
        try:
            return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        except ValueError as e:
            msg = f"Invalid timestamp format: {timestamp}. Expected format: YYYY-MM-DD HH:MM:SS UTC"
            raise ValueError(msg) from e
    return timestamp


def timestamp_with_fractional_seconds(timestamp: datetime | str) -> str:
    """Convert timestamp to string format including fractional seconds.

    Handles multiple input formats and ensures consistent UTC timezone output.

    Args:
        timestamp (datetime | str): Input timestamp either as datetime object or string

    Returns:
        str: Formatted timestamp string in 'YYYY-MM-DD HH:MM:SS.ffffff UTC' format

    Raises:
        ValueError: If string timestamp is in invalid format
    """
    if isinstance(timestamp, str):
        # Try parsing with different formats
        formats = [
            "%Y-%m-%d %H:%M:%S.%f %Z",  # Standard with timezone
            "%Y-%m-%d %H:%M:%S.%f",  # Without timezone
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO format
            "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO with numeric timezone
            # Also try without fractional seconds
            "%Y-%m-%d %H:%M:%S %Z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt).replace(tzinfo=timezone.utc)
                return parsed.strftime("%Y-%m-%d %H:%M:%S.%f %Z")
            except ValueError:
                continue

        msg = f"Invalid timestamp format: {timestamp}"
        raise ValueError(msg)

    # Handle datetime object
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f %Z")


timestamp_to_str_validator = BeforeValidator(timestamp_to_str)
timestamp_with_fractional_seconds_validator = BeforeValidator(timestamp_with_fractional_seconds)
str_to_timestamp_validator = BeforeValidator(str_to_timestamp)


def coerce_to_str_if_uuid(value: UUID | str | None) -> str | None:
    """Convert UUID or string values to strings."""
    # Fast path for common immutable inputs that should be returned unchanged.
    if isinstance(value, str) or value is None:
        return value

    # Attempt to cache only for hashable inputs; if unhashable, bypass the cache to
    # preserve original behavior (no TypeError raised as would happen with lru_cache).
    try:
        key = value
        hash(key)
    except Exception:
        # Unhashable: compute directly and return (preserves original behavior).
        return str(value) if isinstance(value, UUID) else value

    # Cache lookup
    res = _CACHE.get(key, _SENTINEL)
    if res is not _SENTINEL:
        return res

    # Compute result for hashable inputs and store in cache.
    if isinstance(value, UUID):
        res = str(value)
    else:
        res = value

    if len(_CACHE) >= _CACHE_MAXSIZE:
        # Evict an arbitrary item to keep cache bounded. Using next(iter(...))
        # is a fast way to pop a single entry.
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = res
    return res
