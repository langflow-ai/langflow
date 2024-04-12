from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import field_validator, validator
from sqlmodel import Field, Relationship, SQLModel, Column, func, DateTime

if TYPE_CHECKING:
    from langflow.services.database.models.user import User


class ApiKeyBase(SQLModel):
    name: Optional[str] = Field(index=True, nullable=True, default=None)
    created_at: datetime = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    last_used_at: Optional[datetime] = Field(default=None, nullable=True)
    total_uses: int = Field(default=0)
    is_active: bool = Field(default=True)


class ApiKey(ApiKeyBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)

    api_key: str = Field(index=True, unique=True)
    # User relationship
    # Delete API keys when user is deleted
    user_id: UUID = Field(index=True, foreign_key="user.id")
    user: "User" = Relationship(
        back_populates="api_keys",
    )


class ApiKeyCreate(ApiKeyBase):
    api_key: Optional[str] = None
    user_id: Optional[UUID] = None

    @field_validator("created_at", mode="before")
    def set_created_at(cls, v):
        return v or datetime.now(timezone.utc)


class UnmaskedApiKeyRead(ApiKeyBase):
    id: UUID
    api_key: str = Field()
    user_id: UUID = Field()


class ApiKeyRead(ApiKeyBase):
    id: UUID
    api_key: str = Field()
    user_id: UUID = Field()

    @validator("api_key", always=True)
    def mask_api_key(cls, v):
        # This validator will always run, and will mask the API key
        return f"{v[:8]}{'*' * (len(v) - 8)}"
