from datetime import datetime, timezone
from uuid import UUID, uuid4
from pathlib import Path

from pydantic import BaseModel, Field


class File(BaseModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID
    name: str
    path: str
    size: int
    provider: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        orm_mode = True


class UploadFileResponse(BaseModel):
    flow_id: str = Field(serialization_alias="flowId")
    file_path: Path

