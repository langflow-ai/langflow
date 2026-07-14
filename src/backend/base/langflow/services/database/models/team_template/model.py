from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlmodel import JSON, Column, Field, SQLModel


class TeamTemplateStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class TeamTemplate(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "team_template"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, max_length=100)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    category: str = Field(default="all-templates", index=True, max_length=64)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    icon: str | None = Field(default=None, nullable=True)
    gradient: str | None = Field(default=None, nullable=True)
    flow_data: dict = Field(sa_column=Column(JSON, nullable=False))
    source_flow_id: UUID | None = Field(
        default=None,
        sa_column=Column(Uuid(), ForeignKey("flow.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    workspace_id: UUID | None = Field(default=None, nullable=True, index=True)
    created_by: UUID | None = Field(
        default=None,
        sa_column=Column(Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    status: str = Field(default=TeamTemplateStatus.ACTIVE.value, index=True, max_length=16)
    schema_version: int = Field(default=1, nullable=False)
    sanitizer_version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
