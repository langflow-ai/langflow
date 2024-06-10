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
