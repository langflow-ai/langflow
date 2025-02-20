from typing import Any

from loguru import logger
from pydantic import BaseModel, field_serializer, model_serializer, model_validator

from langflow.schema.log import LoggableType
from langflow.serialization import serialize
from langflow.services.tracing.utils import check_string_for_secrets


class Log(BaseModel):
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

    @model_serializer(mode="wrap")
    def serialize_log_without_secrets(self, handler):
        try:
            dump = handler(self)
            message = dump["message"]
            if not isinstance(message, str):
                message = str(message)
            if message.startswith("<Error:"):
                return {"name": self.name, "type": self.type, "message": message}
            try:
                detections, masked_message = check_string_for_secrets(message)
                if detections:
                    message = masked_message
            except (ValueError, TypeError) as e:
                logger.warning("Error checking secrets: %s", str(e))
            dump["message"] = message

        except (ValueError, TypeError) as e:
            return {"name": self.name, "type": self.type, "message": f"<Error: {e!s}>"}
        else:
            return dump

    @model_validator(mode="before")
    @classmethod
    def validate_message(cls, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            return data

        if "message" not in data:
            return data

        message = data["message"]
        try:
            if isinstance(message, bytes):
                try:
                    data["message"] = message.decode("utf-8")
                except UnicodeDecodeError:
                    data["message"] = str(message)
            elif not isinstance(message, str | int | float | bool | dict | list | BaseModel | type(None)):
                try:
                    data["message"] = str(message)
                except (ValueError, TypeError) as e:
                    data["message"] = f"<Error: {e!s}>"
        except (ValueError, TypeError) as e:
            data["message"] = f"<Error: {e!s}>"

        return data
