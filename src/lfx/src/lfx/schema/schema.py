from enum import Enum
from typing import Literal

from pydantic import BaseModel
from typing_extensions import TypedDict

INPUT_FIELD_NAME = "input_value"

InputType = Literal["chat", "text", "any"]
OutputType = Literal["chat", "text", "any", "debug"]


class LogType(str, Enum):
    MESSAGE = "message"
    DATA = "data"
    STREAM = "stream"
    OBJECT = "object"
    ARRAY = "array"
    TEXT = "text"
    UNKNOWN = "unknown"


class StreamURL(TypedDict):
    location: str


class ErrorLog(TypedDict):
    errorMessage: str
    stackTrace: str


class OutputValue(BaseModel):
    message: ErrorLog | StreamURL | dict | list | str
    type: str


def build_output_logs(*args, **kwargs):  # noqa: ARG001
    """Stub function for building output logs."""
    return {}


class InputValueRequest(TypedDict, total=False):
    """Type definition for input value requests."""

    components: list[str] | None
    input_value: str | None
    session: str | None
    type: InputType | None
