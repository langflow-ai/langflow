from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from langflow.services.database.models.credential.schema import CredentialType

if TYPE_CHECKING:
    from langflow.services.database.models.user import User


class CredentialBase(SQLModel):
    name: Optional[str] = Field(None, description="Name of the credential")
    value: Optional[str] = Field(None, description="Encrypted value of the credential")
    provider: Optional[str] = Field(None, description="Provider of the credential (e.g OpenAI)")


class Credential(CredentialBase, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True, description="Unique ID for the credential")
    # name is unique per user
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time of the credential")
    updated_at: Optional[datetime] = Field(None, description="Last update time of the credential")
    # foreign key to user table
    user_id: UUID = Field(description="User ID associated with this credential", foreign_key="user.id")
    user: "User" = Relationship(back_populates="credentials")


class CredentialCreate(CredentialBase):
    # AcceptedProviders is a custom Enum
    provider: CredentialType = Field(description="Provider of the credential (e.g OpenAI)")


class CredentialRead(SQLModel):
    id: UUID
    name: Optional[str] = Field(None, description="Name of the credential")
    provider: Optional[str] = Field(None, description="Provider of the credential (e.g OpenAI)")


class CredentialUpdate(SQLModel):
    id: UUID  # Include the ID for updating
    name: Optional[str] = Field(None, description="Name of the credential")
    value: Optional[str] = Field(None, description="Encrypted value of the credential")
