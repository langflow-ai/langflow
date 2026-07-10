from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import field_validator
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.schema.serialize import UUIDstr
from langflow.services.database.utils import normalize_string_or_none, validate_non_empty_string

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


class TritonServer(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "triton_server"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "name",
            name="uq_triton_server_user_name",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    name: str = Field(description="User-chosen display name, unique per user (e.g. 'staging', 'prod').")
    base_url: str = Field(description="Triton server URL (scheme+host+port), e.g. http://triton:8000.")
    # MUST be stored encrypted by the CRUD layer (auth_utils.encrypt_api_key);
    # the Read schema intentionally excludes this field. Use the dedicated
    # /credentials endpoint to obtain the decrypted value when needed.
    auth_token: str | None = Field(default=None, description="Encrypted bearer token; null when Triton has no auth.")
    notes: str | None = Field(default=None, description="Optional free-form description.")
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    user: "User" = Relationship(back_populates="triton_servers")

    @field_validator("name", "base_url")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)

    @field_validator("auth_token", "notes")
    @classmethod
    def normalize_optional(cls, v: str | None) -> str | None:
        return normalize_string_or_none(v)


class TritonServerCreate(SQLModel):
    name: str
    base_url: str
    auth_token: str | None = None
    notes: str | None = None


class TritonServerRead(SQLModel):
    id: UUID
    user_id: UUID
    name: str
    base_url: str
    notes: str | None = None
    has_auth_token: bool = False
    created_at: datetime
    updated_at: datetime


class TritonServerUpdate(SQLModel):
    name: str | None = None
    base_url: str | None = None
    auth_token: str | None = None
    notes: str | None = None


class TritonServerCredentials(SQLModel):
    auth_token: str | None = None
