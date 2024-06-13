from collections import defaultdict
from typing import Any, Literal

from typing_extensions import TypedDict

INPUT_FIELD_NAME = "input_value"

InputType = Literal["chat", "text", "any"]
OutputType = Literal["chat", "text", "any", "debug"]


class StreamURL(TypedDict):
    location: str


class Log(TypedDict):
    message: str | dict | StreamURL | list
    type: str


def build_logs_from_artifacts(artifacts: dict) -> dict:
    logs = defaultdict(list)
    for key in artifacts:
        message = artifacts[key]["raw"]
        _type = artifacts[key]["type"]

        if not isinstance(message, dict):
            message = {"message": message}

        if "stream_url" in message and "type" in message:
            stream_url = StreamURL(location=message["stream_url"])
            log = Log(message=stream_url, type=_type)
        elif _type:
            log = Log(message=message, type=_type)

        logs[key].append(log)
    return logs


def build_log_from_raw_and_type(raw: Any, log_type: str) -> Log:
    return Log(message=raw, type=log_type)
