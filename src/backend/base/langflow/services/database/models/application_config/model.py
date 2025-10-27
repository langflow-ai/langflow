from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, SQLModel, Text, UniqueConstraint, func

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def utc_now():
    return datetime.now(timezone.utc)


class ApplicationConfigBase(SQLModel):
    key: str = Field(description="Configuration key (e.g., 'app-logo')", index=True)
    value: str = Field(description="Configuration value (e.g., blob storage URL)", sa_column=Column(Text, nullable=False))
    type: str | None = Field(default="string", description="Type of value (string, json, etc.)")
    description: str | None = Field(default=None, description="Description of this configuration")


class ApplicationConfig(ApplicationConfigBase, table=True):  # type: ignore[call-arg]
    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the configuration",
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the configuration",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last update time of the configuration",
    )
    updated_by: UUID | None = Field(
        default=None, foreign_key="user.id", description="User who last updated this configuration"
    )

    __tablename__ = "application_config"
    __table_args__ = (UniqueConstraint("key", name="unique_config_key"),)


class ApplicationConfigCreate(ApplicationConfigBase):
    created_at: datetime | None = Field(default_factory=utc_now, description="Creation time of the configuration")
    updated_at: datetime | None = Field(default_factory=utc_now, description="Update time of the configuration")


class ApplicationConfigRead(SQLModel):
    id: UUID
    key: str
    value: str
    type: str | None = None
    description: str | None = None
    created_at: datetime | None
    updated_at: datetime | None


class ApplicationConfigUpdate(SQLModel):
    value: str = Field(description="Configuration value to update")
    description: str | None = Field(None, description="Description to update")
