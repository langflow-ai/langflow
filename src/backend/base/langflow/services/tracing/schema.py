from typing import Any

from pydantic import field_serializer

from langflow.schema.log import LoggableType
from langflow.schema.secrets import DataRedactionModel
from langflow.serialization import serialize


class Log(DataRedactionModel):
    name: str
    message: LoggableType
    type: str

    @field_serializer("message", when_used="always")
    @classmethod
    def serialize_message(cls, value: Any) -> str:
        try:
            if isinstance(value, int | float | bool):
                return str(value)
            if isinstance(value, bytes):
                try:
                    return value.decode("utf-8")
                except UnicodeDecodeError:
                    return str(value)
            if hasattr(value, "__repr__"):
                try:
                    return str(value)
                except (ValueError, TypeError) as e:
                    return f"<Error: {e!s}>"
            return serialize(value)
        except (ValueError, TypeError) as e:
            return f"<Error: {e!s}>"
