from typing import Any

from pydantic import BaseModel, Field

class TaskResponse(BaseModel):
    id: str | None = Field(None)
    href: str | None = Field(None)

class TaskStatusResponse(BaseModel):
    status: str
    result: Any | None = None

class ProcessResponse(BaseModel):
    result: Any
    status: str | None = None
    task: TaskResponse | None = None
    session_id: str | None = None
    backend: str | None = None