from collections.abc import Generator
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pandas import Series
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict

if TYPE_CHECKING:
    from lfx.custom.custom_component.component import Component

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


def get_type(payload):
    # Importing here to avoid circular imports
    from lfx.schema.data import Data
    from lfx.schema.dataframe import DataFrame
    from lfx.schema.message import Message

    result = LogType.UNKNOWN
    match payload:
        case Message():
            result = LogType.MESSAGE

        case Data():
            result = LogType.DATA

        case dict():
            result = LogType.OBJECT

        case list() | DataFrame():
            result = LogType.ARRAY

        case str():
            result = LogType.TEXT

    if result == LogType.UNKNOWN and (
        (payload and isinstance(payload, Generator))
        or (isinstance(payload, Message) and isinstance(payload.text, Generator))
    ):
        result = LogType.STREAM

    return result


def get_message(payload):
    # Importing here to avoid circular imports
    from lfx.schema.data import Data

    message = None
    if hasattr(payload, "data"):
        message = payload.data

    elif hasattr(payload, "model_dump"):
        message = payload.model_dump()

    if message is None and isinstance(payload, dict | str | Data):
        message = payload.data if isinstance(payload, Data) else payload

    if isinstance(message, Series):
        return message if not message.empty else payload

    return message or payload


def build_output_logs(vertex, result) -> dict:
    """Build output logs from vertex outputs and results."""
    # Importing here to avoid circular imports
    from lfx.schema.dataframe import DataFrame
    from lfx.serialization.serialization import serialize

    outputs: dict[str, OutputValue] = {}
    component_instance: Component = result[0]
    for index, output in enumerate(vertex.outputs):
        if component_instance.status is None:
            payload = component_instance.get_results()
            output_result = payload.get(output["name"])
        else:
            payload = component_instance.get_artifacts()
            output_result = payload.get(output["name"], {}).get("raw")
        message = get_message(output_result)
        type_ = get_type(output_result)

        match type_:
            case LogType.STREAM if "stream_url" in message:
                message = StreamURL(location=message["stream_url"])

            case LogType.STREAM:
                message = ""

            case LogType.MESSAGE if hasattr(message, "message"):
                message = message.message

            case LogType.UNKNOWN:
                message = ""

            case LogType.ARRAY:
                if isinstance(message, DataFrame):
                    message = message.to_dict(orient="records")
                message = [serialize(item) for item in message]
        name = output.get("name", f"output_{index}")
        outputs |= {name: OutputValue(message=message, type=type_).model_dump()}

    return outputs


class BuildStatus(BaseModel):
    """Build status schema for API compatibility."""

    status: str
    message: str | None = None
    progress: float | None = None


class InputValueRequest(BaseModel):
    components: list[str] | None = []
    input_value: str | None = None
    session: str | None = None
    type: InputType | None = Field(
        "any",
        description="Defines on which components the input value should be applied. "
        "'any' applies to all input components.",
    )
    client_request_time: int | None = Field(
        None,
        description="Client-side timestamp in milliseconds when the request was initiated. "
        "Used to calculate accurate end-to-end duration.",
    )

    # add an example
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "components": ["components_id", "Component Name"],
                    "input_value": "input_value",
                    "session": "session_id",
                },
                {"components": ["Component Name"], "input_value": "input_value"},
                {"input_value": "input_value"},
                {
                    "components": ["Component Name"],
                    "input_value": "input_value",
                    "session": "session_id",
                },
                {"input_value": "input_value", "session": "session_id"},
                {"type": "chat", "input_value": "input_value"},
                {"type": "json", "input_value": '{"key": "value"}'},
            ]
        },
        extra="forbid",
    )
