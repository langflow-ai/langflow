from typing import TypeAlias

from pydantic import BaseModel
from typing_extensions import Protocol

from langflow.schema.playground_events import PlaygroundEvent

LoggableType: TypeAlias = str | dict | list | int | float | bool | None | BaseModel | PlaygroundEvent


class LogFunctionType(Protocol):
    def __call__(self, message: LoggableType | list[LoggableType], *, name: str | None = None) -> None: ...
