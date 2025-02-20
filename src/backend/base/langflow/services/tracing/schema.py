import logging
from typing import Any

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import default_settings
from pydantic import BaseModel, field_serializer, model_serializer, model_validator

from langflow.schema.log import LoggableType
from langflow.serialization import serialize

logger = logging.getLogger(__name__)

# Constants
MIN_SECRET_LENGTH = 8


def check_string_for_secrets(s: str | float | bool | None) -> tuple[list, str]:
    """Check a string for secrets using scan_line and return both the detections and a string with secrets replaced.

    Args:
        s: The input string to check for secrets

    Returns:
        A tuple containing:
        - list: List of detected secrets (PotentialSecret objects)
        - str: The input string with any detected secrets replaced with a standard message
    """
    if s is None:
        return [], ""

    # Convert non-string input to string
    s_str = str(s)

    # Use detect-secrets to find secrets
    with default_settings():
        detections = list(scan_line(s_str))

    # If no secrets found, return original string
    if not detections:
        return [], s_str

    # Filter out false positives
    valid_detections = []
    for detection in detections:
        if not hasattr(detection, "secret_value") or not detection.secret_value:
            continue

        secret_str = str(detection.secret_value)
        # Skip if secret is too short or just numbers
        if len(secret_str) < MIN_SECRET_LENGTH or secret_str.isdigit():
            continue

        valid_detections.append(detection)

    if not valid_detections:
        return [], s_str

    # Return the fixed string for any valid detection
    return valid_detections, "[Secret Redacted]"


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
