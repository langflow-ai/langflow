from datetime import datetime, timezone
from uuid import UUID

from pydantic import BeforeValidator

# An ordered list of timestamp formats to try to parse from str, from most to least specific
TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S.%f %Z",  # Standard with timezone and microseconds
    "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO with numeric timezone and microseconds
    "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
    "%Y-%m-%d %H:%M:%S.%f",  # Without timezone, with microseconds
    "%Y-%m-%d %H:%M:%S %Z",  # Standard with timezone
    "%Y-%m-%dT%H:%M:%S%z",  # ISO with numeric timezone
    "%Y-%m-%dT%H:%M:%S",  # ISO format
    "%Y-%m-%d %H:%M:%S",  # Without timezone
]

# Formats that carry their own timezone offset — must use astimezone, not replace
_FORMATS_WITH_NUMERIC_TZ = {"%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"}

TF_WITH_TZ_AND_MICROSECONDS = "%Y-%m-%d %H:%M:%S.%f %Z"


def timestamp_to_str(timestamp: datetime | str) -> str:
    """Convert timestamp to standardized string format.

    Handles multiple input formats and ensures consistent UTC timezone output.

    Args:
        timestamp (datetime | str): Input timestamp either as datetime object or string

    Returns:
        str: Formatted timestamp string in 'YYYY-MM-DD HH:MM:SS.ffffff UTC' format

    Raises:
        ValueError: If string timestamp is in invalid format
    """
    if isinstance(timestamp, str):
        for fmt in TIMESTAMP_FORMATS:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt)  # noqa: DTZ007
                if fmt in _FORMATS_WITH_NUMERIC_TZ:
                    parsed = parsed.astimezone(timezone.utc)
                else:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.strftime(TF_WITH_TZ_AND_MICROSECONDS)
            except ValueError:
                continue

        msg = f"Invalid timestamp format: {timestamp}"
        raise ValueError(msg)

    # Handle datetime object
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.strftime(TF_WITH_TZ_AND_MICROSECONDS)


def str_to_timestamp(timestamp: str | datetime) -> datetime:
    """Convert timestamp to datetime object.

    Handles multiple input formats and ensures consistent UTC timezone output.

    Args:
        timestamp (str | datetime): Input timestamp either as string or datetime object

    Returns:
        datetime: Datetime object with UTC timezone

    Raises:
        ValueError: If string timestamp is not in a recognised format
    """
    if isinstance(timestamp, str):
        for fmt in TIMESTAMP_FORMATS:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt)  # noqa: DTZ007
                if fmt in _FORMATS_WITH_NUMERIC_TZ:
                    return parsed.astimezone(timezone.utc)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        msg = f"Invalid timestamp format: {timestamp}. Expected format: YYYY-MM-DD HH:MM:SS.ffffff UTC"
        raise ValueError(msg)
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
    return timestamp_to_str(timestamp)


timestamp_to_str_validator = BeforeValidator(timestamp_to_str)
timestamp_with_fractional_seconds_validator = BeforeValidator(timestamp_with_fractional_seconds)
str_to_timestamp_validator = BeforeValidator(str_to_timestamp)


def uuid_validator(uuid_str: str | UUID, message: str | None = None) -> UUID:
    if isinstance(uuid_str, UUID):
        return uuid_str
    try:
        return UUID(uuid_str)
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(message or f"Invalid UUID: {uuid_str}") from e


def null_check_validator(value: str | None, message: str | None = None) -> str | None:
    if value is None:
        raise ValueError(message or "Value is required")
    return value
