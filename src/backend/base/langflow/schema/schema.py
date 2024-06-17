from typing import Literal

from typing_extensions import TypedDict

INPUT_FIELD_NAME = "input_value"

InputType = Literal["chat", "text", "any"]
OutputType = Literal["chat", "text", "any", "debug"]


class StreamURL(TypedDict):
    location: str


class Log(TypedDict):
    message: str | dict | StreamURL | list
    type: str


def build_logs(vertex) -> dict:
    logs = {}
    for key in vertex.artifacts:
        message = vertex.artifacts[key]["raw"]
        _type = vertex.artifacts[key]["type"]

        if "stream_url" in message and "type" in message:
            stream_url = StreamURL(location=message["stream_url"])
            log = Log(message=stream_url, type=_type)
        elif _type:
            log = Log(message=message, type=_type)

        logs[key] = [log]
    return logs
