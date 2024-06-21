from typing_extensions import TypedDict


class Log(TypedDict):
    name: str
    message: list | dict | str
    type: str
