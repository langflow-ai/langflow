from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlmodel import Column, Field, Relationship, UniqueConstraint

from langflow.schema.serialize import UUIDstr
from langflow.services.database.models.base import LangflowBaseModel

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


class File(LangflowBaseModel, table=True):  # type: ignore[call-arg]
    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False))
    user: "User" = Relationship(back_populates="files")
    name: str = Field(nullable=False)
    path: str = Field(nullable=False)
    size: int = Field(nullable=False)
    provider: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("name", "user_id"),)
