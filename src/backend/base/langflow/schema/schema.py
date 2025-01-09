from collections.abc import Generator
from enum import Enum
from typing import Literal

from pydantic import BaseModel
from typing_extensions import TypedDict

from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.schema.serialize import recursive_serialize_or_str

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
    match payload:
        case Message():
            return LogType.MESSAGE

        case Data():
            return LogType.DATA

        case dict():
            return LogType.OBJECT

        case list() | DataFrame():
            return LogType.ARRAY

        case str():
            return LogType.TEXT

        case Generator():
            return LogType.STREAM

    return LogType.UNKNOWN


def get_message(payload):
    if hasattr(payload, "data"):
        return payload.data
    if hasattr(payload, "model_dump"):
        return payload.model_dump()

    if isinstance(payload, (dict | str | Data)):
        return payload.data if isinstance(payload, Data) else payload

    return payload


def build_output_logs(vertex, result) -> dict:
    outputs: dict[str, OutputValue] = {}
    component_instance = result[0]

    for index, output in enumerate(vertex.outputs):
        payload = (
            component_instance._results.get(output["name"])
            if component_instance.status is None
            else component_instance._artifacts.get(output["name"], {}).get("raw")
        )

        message = get_message(payload)
        type_ = get_type(payload)

        match type_:
            case LogType.STREAM:
                message = StreamURL(location=message["stream_url"]) if "stream_url" in message else ""
            case LogType.MESSAGE if hasattr(message, "message"):
                message = message.message
            case LogType.UNKNOWN:
                message = ""

            case LogType.ARRAY:
                if isinstance(message, DataFrame):
                    message = message.to_dict(orient="records")
                message = [recursive_serialize_or_str(item) for item in message]

        name = output.get("name", f"output_{index}")
        outputs[name] = OutputValue(message=message, type=type_).model_dump()

    return outputs
