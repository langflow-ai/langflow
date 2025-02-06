from collections.abc import Generator
from enum import Enum
from typing import Literal

from pydantic import BaseModel
from typing_extensions import TypedDict

from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.serialization.serialization import \
    serialize as original_serialize

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
    if isinstance(payload, Message):
        return LogType.MESSAGE
    if isinstance(payload, Data):
        return LogType.DATA
    if isinstance(payload, dict):
        return LogType.OBJECT
    if isinstance(payload, (list, DataFrame)):
        return LogType.ARRAY
    if isinstance(payload, str):
        return LogType.TEXT
    if isinstance(payload, Generator) or (isinstance(payload, Message) and isinstance(payload.text, Generator)):
        return LogType.STREAM
    return LogType.UNKNOWN


def get_message(payload):
    if hasattr(payload, "data"):
        return payload.data
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if isinstance(payload, (dict, str, Data)):
        return payload.data if isinstance(payload, Data) else payload
    return payload


def build_output_logs(vertex, result) -> dict:
    outputs = {}
    component_instance = result[0]
    for index, output in enumerate(vertex.outputs):
        payload = component_instance._results if component_instance.status is None else component_instance._artifacts
        output_result = (
            payload.get(output["name"], {}).get("raw") if component_instance.status else payload.get(output["name"])
        )
        message = get_message(output_result)
        type_ = get_type(output_result)

        if type_ == LogType.STREAM:
            if isinstance(message, dict) and "stream_url" in message:
                message = StreamURL(location=message["stream_url"])
            else:
                message = ""

        elif type_ == LogType.MESSAGE and hasattr(message, "message"):
            message = message.message

        elif type_ in {LogType.UNKNOWN, LogType.ARRAY}:
            if isinstance(message, DataFrame):
                message = message.to_dict(orient="records")
            message = [original_serialize(item) for item in message]

        name = output.get("name", f"output_{index}")
        outputs[name] = OutputValue(message=message, type=type_).model_dump()

    return outputs
