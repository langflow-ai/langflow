"""Credential model for model provider credentials."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel

from langflow.schema.serialize import UUIDstr

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


class CredentialBase(SQLModel):
    """Base credential model."""

    name: str = Field(description="Name of the credential")
    provider: str = Field(description="Model provider name (e.g., 'OpenAI', 'Anthropic')")
    description: str | None = Field(default=None, description="Optional description")
    is_active: bool = Field(default=True, description="Whether the credential is active")
    usage_count: int = Field(default=0, description="Number of times credential was used")
    last_used: datetime | None = Field(default=None, description="Last time credential was used")


class Credential(CredentialBase, table=True):  # type: ignore[call-arg]
    """Credential database model."""

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True, unique=True)
    encrypted_value: str = Field(description="Encrypted credential value")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation time")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update time")

    # User relationship
    user_id: UUIDstr = Field(foreign_key="user.id", description="User ID")
    user: "User" = Relationship(back_populates="credentials")


class CredentialCreate(CredentialBase):
    """Schema for creating a credential."""

    value: str = Field(description="Plain text credential value")


class CredentialRead(CredentialBase):
    """Schema for reading a credential (without encrypted value)."""

    id: UUIDstr
    created_at: datetime
    updated_at: datetime
    last_used: datetime | None = None


class CredentialUpdate(BaseModel):
    """Schema for updating a credential."""

    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    value: str | None = None  # New credential value if updating
