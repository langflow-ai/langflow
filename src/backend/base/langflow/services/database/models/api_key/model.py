from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func
from langflow.utils.constants import API_KEY_EXPIRATION_HOURS

if TYPE_CHECKING:
    from langflow.services.database.models.user import User


def utc_now():
    return datetime.now(timezone.utc)


def expire_time():
    return utc_now() + timedelta(hours=API_KEY_EXPIRATION_HOURS)


class ApiKeyBase(SQLModel):
    name: Optional[str] = Field(index=True, nullable=True, default=None)
    last_used_at: Optional[datetime] = Field(default=None, nullable=True)
    total_uses: int = Field(default=0)
    is_active: bool = Field(default=True)


class ApiKey(ApiKeyBase, table=True):  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    expire_at: Optional[datetime] = Field(
        default_factory=expire_time, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    api_key: str = Field(index=True, unique=True)
    # User relationship
    # Delete API keys when user is deleted
    user_id: UUID = Field(index=True, foreign_key="user.id")
    user: "User" = Relationship(
        back_populates="api_keys",
    )
    # Flow relationship (optional)
    # Delete API keys when flow is deleted
    flow_id: Optional[UUID] = Field(default=None, foreign_key="flow.id", nullable=True)
    flow: Optional["Flow"] = Relationship()


class ApiKeyCreate(ApiKeyBase):
    api_key: Optional[str] = None
    user_id: Optional[UUID] = None
    created_at: Optional[datetime] = Field(default_factory=utc_now)
    expire_at: Optional[datetime] = Field(default_factory=expire_time)
    flow_id: Optional[UUID] = None

    @field_validator("expire_at", mode="before")
    @classmethod
    def set_expire_at(cls, v):
        return v or expire_time()

    @field_validator("created_at", mode="before")
    @classmethod
    def set_created_at(cls, v):
        return v or utc_now()


class UnmaskedApiKeyRead(ApiKeyBase):
    id: UUID
    api_key: str = Field()
    user_id: UUID = Field()
    created_at: datetime = Field()
    expire_at: datetime = Field()
    flow_id: Optional[UUID] = Field(default=None)


class ApiKeyRead(ApiKeyBase):
    id: UUID
    api_key: str = Field(schema_extra={"validate_default": True})
    user_id: UUID = Field()
    created_at: datetime = Field()
    expire_at: datetime = Field()
    flow_id: Optional[UUID] = Field(default=None)

    @field_validator("api_key")
    @classmethod
    def mask_api_key(cls, v):
        # This validator will always run, and will mask the API key
        return f"{v[:8]}{'*' * (len(v) - 8)}"
