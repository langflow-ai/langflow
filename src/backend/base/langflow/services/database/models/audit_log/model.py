"""One append-only row per attempt against a resource.

Deliberately resource-agnostic: nothing here names a flow. A new resource is a
new ``resource_type`` value and new event names, never a migration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, field_serializer, field_validator
from sqlalchemy import Column, Index
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class AuditLog(SQLModel, table=True):  # type: ignore[call-arg]
    """Who changed what, when, whether it worked, and which fields were touched."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_resource", "resource_type", "resource_id", "created_at"),
        Index("ix_audit_log_user", "user_id", "created_at"),
        Index("ix_audit_log_event", "event", "created_at"),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    # Server-side so every replica shares one clock: a pod's own clock can drift,
    # and an audit trail ordered by a skewed timestamp misleads the reader.
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    event: str = Field(nullable=False)
    # Deliberately no foreign key: attribution has to survive deleting the user.
    user_id: UUIDstr | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    resource_type: str = Field(nullable=False)
    resource_id: UUIDstr | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    payload: dict | None = Field(default=None, sa_column=Column(sa.JSON))


def as_utc(value: datetime) -> datetime:
    """Attach UTC to a naive timestamp.

    SQLite returns ``server_default=now()`` without a timezone while PostgreSQL
    returns it with one, and the same column must not read differently per
    backend.
    """
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class AuditLogRead(BaseModel):
    """One audit row as the API returns it."""

    model_config = {"from_attributes": True}

    id: UUIDstr
    created_at: datetime
    event: str
    user_id: UUIDstr | None = None
    username: str | None = None
    resource_type: str
    resource_id: UUIDstr | None = None
    payload: dict[str, Any] | None = None

    @field_validator("created_at", mode="after")
    @classmethod
    def _normalize_timezone(cls, value: datetime) -> datetime:
        return as_utc(value)

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return as_utc(value).isoformat()


class AuditLogListResponse(BaseModel):
    """A page of audit rows, newest first."""

    entries: list[AuditLogRead]
    total: int
