from datetime import datetime

from pydantic import BeforeValidator


def timestamp_to_str(timestamp: datetime | str) -> str:
    if isinstance(timestamp, str):
        # Just check if the string is a valid datetime
        try:
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S %Z")  # noqa: DTZ007
            result = timestamp
        except ValueError as e:
            msg = f"Invalid timestamp: {timestamp}"
            raise ValueError(msg) from e
    else:
        result = timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")
    return result


def timestamp_with_fractional_seconds(timestamp: datetime | str) -> str:
    if isinstance(timestamp, str):
        # Just check if the string is a valid datetime
        try:
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f %Z")  # noqa: DTZ007
            result = timestamp
        except ValueError as e:
            msg = f"Invalid timestamp: {timestamp}"
            raise ValueError(msg) from e
    else:
        result = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f %Z")
    return result


timestamp_to_str_validator = BeforeValidator(timestamp_to_str)
timestamp_with_fractional_seconds_validator = BeforeValidator(timestamp_with_fractional_seconds)
