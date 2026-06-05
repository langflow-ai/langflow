from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import field_serializer, field_validator
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.schema.serialize import UUIDstr

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def utc_now():
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def _as_utc_iso(v: datetime | None) -> str | None:
    # SQLite (and pre-migration Postgres rows) return naive datetimes from a
    # timezone=True column. Every writer in this codebase persists UTC, so
    # treat naive values as UTC rather than letting Pydantic emit them without
    # an offset — JS Date() parses an offset-less ISO string as local time,
    # which shifts the displayed expiry by the viewer's UTC offset.
    if v is None:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v.replace(microsecond=0).isoformat()


class ApiKeyBase(SQLModel):
    name: str | None = Field(index=True, nullable=True, default=None)
    last_used_at: datetime | None = Field(default=None, nullable=True)
    total_uses: int = Field(default=0)
    is_active: bool = Field(default=True)
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    @field_serializer("expires_at", "last_used_at", when_used="always")
    def _serialize_expires_last_used(self, v: datetime | None) -> str | None:
        return _as_utc_iso(v)


class ApiKey(ApiKeyBase, table=True):  # type: ignore[call-arg]
    id: UUIDstr = Field(default_factory=uuid4, primary_key=True, unique=True)
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    api_key: str = Field(index=True, unique=True)
    api_key_hash: str | None = Field(default=None, index=True)
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
        """Default created_at to the current UTC time when not provided."""
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
        """Mask all but the first 8 characters of the API key."""
        return f"{v[:8]}{'*' * (len(v) - 8)}"

    @field_serializer("created_at", when_used="always")
    def _serialize_created_at(self, v: datetime) -> str | None:
        return _as_utc_iso(v)
