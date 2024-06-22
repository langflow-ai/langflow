from typing_extensions import TypedDict

from langflow.schema.log import LoggableType


class Log(TypedDict):
    name: str
    message: LoggableType
    type: str
