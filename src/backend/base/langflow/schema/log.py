from typing import Union

from pydantic import BaseModel

LoggableType = Union[str, dict, list, int, float, bool, None, BaseModel]
