from typing import Optional, Union

from pydantic import BaseModel
from typing_extensions import Protocol

LoggableType = Union[str, dict, list, int, float, bool, None, BaseModel]


class LogFunctionType(Protocol):
    def __call__(self, message: Union[LoggableType, list[LoggableType]], *, name: Optional[str] = None) -> None: ...
