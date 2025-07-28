from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def utc_now():
    return datetime.now(timezone.utc)


class InstallationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PackageInstallationBase(SQLModel):
    package_name: str = Field(description="Name of the package being installed")
    status: InstallationStatus = Field(default=InstallationStatus.PENDING, description="Installation status")
    message: str | None = Field(default=None, description="Installation result message")


class PackageInstallation(PackageInstallationBase, table=True):  # type: ignore[call-arg]
    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the package installation",
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the installation record",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last update time of the installation record",
    )
    # foreign key to user table
    user_id: UUID = Field(description="User ID who initiated the installation", foreign_key="user.id")
    user: "User" = Relationship(back_populates="package_installations")


class PackageInstallationCreate(PackageInstallationBase):
    user_id: UUID = Field(description="User ID who initiated the installation")
    created_at: datetime | None = Field(default_factory=utc_now, description="Creation time")
    updated_at: datetime | None = Field(default_factory=utc_now, description="Update time")


class PackageInstallationRead(SQLModel):
    id: UUID
    package_name: str
    status: InstallationStatus
    message: str | None
    created_at: datetime | None
    updated_at: datetime | None
    user_id: UUID


class PackageInstallationUpdate(SQLModel):
    status: InstallationStatus | None = Field(default=None, description="Updated installation status")
    message: str | None = Field(default=None, description="Updated installation message")
    updated_at: datetime | None = Field(default_factory=utc_now, description="Update time")
