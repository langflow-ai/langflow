from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import field_validator
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.schema.serialize import UUIDstr

if TYPE_CHECKING:
    from langflow.services.database.models.user import User


def utc_now():
    return datetime.now(timezone.utc)


class ApiKeyBase(SQLModel):
    name: str | None = Field(index=True, nullable=True, default=None)
    last_used_at: datetime | None = Field(default=None, nullable=True)
    total_uses: int = Field(default=0)
    is_active: bool = Field(default=True)


class ApiKey(ApiKeyBase, table=True):  # type: ignore[call-arg]
    id: UUIDstr = Field(default_factory=uuid4, primary_key=True, unique=True)
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    api_key: str = Field(index=True, unique=True)
    # User relationship
    # Delete API keys when user is deleted
    user_id: UUIDstr = Field(index=True, foreign_key="user.id")
    user: "User" = Relationship(
        back_populates="api_keys",
    )


class ApiKeyCreate(ApiKeyBase):
    api_key: str | None = None
    user_id: UUIDstr | None = None
    created_at: datetime | None = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def set_created_at(cls, v):
        return v or utc_now()


class UnmaskedApiKeyRead(ApiKeyBase):
    id: UUIDstr
    api_key: str = Field()
    user_id: UUIDstr = Field()


class ApiKeyRead(ApiKeyBase):
    id: UUIDstr
    api_key: str = Field(schema_extra={"validate_default": True})
    user_id: UUIDstr = Field()
    created_at: datetime = Field()

    @field_validator("api_key")
    @classmethod
    def mask_api_key(cls, v) -> str:
        # This validator will always run, and will mask the API key
        return f"{v[:8]}{'*' * (len(v) - 8)}"
