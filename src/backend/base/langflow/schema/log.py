from typing import TypeAlias

from pydantic import BaseModel
from typing_extensions import Protocol

LoggableType: TypeAlias = str | dict | list | int | float | bool | None | BaseModel


class LogFunctionType(Protocol):
    def __call__(self, message: LoggableType | list[LoggableType], *, name: str | None = None) -> None: ...
