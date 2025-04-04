from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr
from langflow.services.settings.utils import get_current_time_with_timezone


class File(SQLModel, table=True):  # type: ignore[call-arg]
    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    name: str = Field(unique=True, nullable=False)
    path: str = Field(nullable=False)
    size: int = Field(nullable=False)
    provider: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: get_current_time_with_timezone())
    updated_at: datetime = Field(default_factory=lambda: get_current_time_with_timezone())
