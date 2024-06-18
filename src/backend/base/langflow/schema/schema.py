from enum import Enum
from typing import Generator, Literal, Union

from pydantic import BaseModel

from langflow.schema import Data
from langflow.schema.message import Message

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


class StreamURL(BaseModel):
    location: str


class Log(BaseModel):
    message: Union[StreamURL, dict, list, str]
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

        case list():
            result = LogType.ARRAY

        case str():
            result = LogType.TEXT

    if result == LogType.UNKNOWN:
        if payload and isinstance(payload, Generator):
            result = LogType.STREAM

        elif isinstance(payload, Message) and isinstance(payload.text, Generator):
            result = LogType.STREAM

    return result


def get_message(payload):
    message = None
    if hasattr(payload, "data"):
        message = payload.data

    elif hasattr(payload, "model_dump"):
        message = payload.model_dump()

    if message is None and isinstance(payload, (dict, str, Data)):
        message = payload.data if isinstance(payload, Data) else payload

    return message or payload


def build_logs(vertex, result) -> dict:
    logs = dict()
    payload = result[0]._results
    for index, output in enumerate(vertex.outputs):
        output_result = payload.get(output["name"])
        message = get_message(output_result)
        _type = get_type(output_result)

        match _type:
            case LogType.STREAM if "stream_url" in message:
                message = StreamURL(location=message["stream_url"])

            case LogType.STREAM:
                message = ""

            case LogType.MESSAGE if hasattr(message, "message"):
                message = message.message

            case LogType.UNKNOWN if message is None:
                message = ""

        name = output.get("name", f"output_{index}")
        logs |= {name: Log(message=message, type=_type).model_dump()}

    return logs
