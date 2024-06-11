from collections import defaultdict
from typing import Literal

from typing_extensions import TypedDict

INPUT_FIELD_NAME = "input_value"

InputType = Literal["chat", "text", "any"]
OutputType = Literal["chat", "text", "any", "debug"]


class StreamURL(TypedDict):
    location: str


class Log(TypedDict):
    message: str | dict | StreamURL
    type: str


def build_logs_from_artifacts(artifacts: dict) -> dict:
    logs = defaultdict(list)
    for key in artifacts:
        message = artifacts[key]

        if not isinstance(message, dict):
            message = {"message": message}

        if "stream_url" in message and "type" in message:
            stream_url = StreamURL(location=message["stream_url"])
            log = Log(message=stream_url, type=message["type"])
        elif "type" in message:
            log = Log(message=message, type=message["type"])

        logs[key].append(log)

    return logs
