from collections.abc import Generator
from enum import Enum
from typing import Literal

from pydantic import BaseModel
from typing_extensions import TypedDict

from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.serialization.serialization import serialize

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
    message = None
    if hasattr(payload, "data"):
        message = payload.data

    elif hasattr(payload, "model_dump"):
        message = payload.model_dump()

    if message is None and isinstance(payload, dict | str | Data):
        message = payload.data if isinstance(payload, Data) else payload

    return message or payload


def build_output_logs(vertex, result) -> dict:
    outputs: dict[str, OutputValue] = {}
    component_instance = result[0]
    for index, output in enumerate(vertex.outputs):
        if component_instance.status is None:
            payload = component_instance._results
            output_result = payload.get(output["name"])
        else:
            payload = component_instance._artifacts
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
