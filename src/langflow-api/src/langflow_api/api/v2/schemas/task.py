from typing import Any

from pydantic import BaseModel

class TaskStatusResponse(BaseModel):
    status: str
    result: Any | None = None
