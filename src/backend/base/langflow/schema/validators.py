from datetime import datetime, timezone

from pydantic import BeforeValidator

TF_WITH_TZ_AND_MICROSECONDS = "%Y-%m-%d %H:%M:%S.%f %Z"
TF_WITH_TZ_AND_MICROSECONDS_ISO = "%Y-%m-%dT%H:%M:%S.%f%z"

# An ordered list of timestamp formats to try to parse from str, from most to least specific
TIMESTAMP_FORMATS = [
    TF_WITH_TZ_AND_MICROSECONDS,  # Standard with timezone and microseconds
    TF_WITH_TZ_AND_MICROSECONDS_ISO,  # ISO with numeric timezone and microseconds
    "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
    "%Y-%m-%d %H:%M:%S.%f",  # Without timezone, with microseconds
    "%Y-%m-%d %H:%M:%S %Z",  # Standard with timezone
    "%Y-%m-%dT%H:%M:%S%z",  # ISO with numeric timezone
    "%Y-%m-%dT%H:%M:%S",  # ISO format
    "%Y-%m-%d %H:%M:%S",  # Without timezone
]

# Formats that carry their own timezone offset — must use astimezone, not replace
_FORMATS_WITH_NUMERIC_TZ = {TF_WITH_TZ_AND_MICROSECONDS_ISO, "%Y-%m-%dT%H:%M:%S%z"}


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


timestamp_to_str_validator = BeforeValidator(timestamp_to_str)
str_to_timestamp_validator = BeforeValidator(str_to_timestamp)
