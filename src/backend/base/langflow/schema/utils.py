from datetime import datetime

from pydantic import BeforeValidator


def timestamp_to_str(timestamp: datetime | str) -> str:
    if isinstance(timestamp, str):
        # Just check if the string is a valid datetime
        try:
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
            return timestamp
        except ValueError as e:
            msg = f"Invalid timestamp: {timestamp}"
            raise ValueError(msg) from e
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


timestamp_to_str_validator = BeforeValidator(timestamp_to_str)
