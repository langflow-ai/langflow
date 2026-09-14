"""One append-only row per attempt against a resource.

Deliberately resource-agnostic: nothing here names a flow. A new resource is a
new ``resource_type`` value and new event names, never a migration.

Two families share the table. An ``authz`` row records a decision about whether
an attempt was permitted; an ``action`` row records what the attempt did. They
are kept apart because a reader asking "who was refused" and a reader asking
"what changed" are asking different questions, and because a denial must never
be mistaken for a mutation that happened.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, field_serializer, field_validator
from sqlalchemy import CheckConstraint, Column, Index
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class AuditFamily(str, Enum):
    """Which question a row answers."""

    AUTHZ = "authz"
    ACTION = "action"


class AuditResult(str, Enum):
    """How the attempt ended.

    ``allow`` / ``deny`` belong to ``authz``; ``succeeded`` / ``failed`` to
    ``action``. The pairing is enforced in ``recorder``: a constraint covering
    the union cannot express it, and a row that crosses the families would make
    every "show me the denials" query wrong.
    """

    ALLOW = "allow"
    DENY = "deny"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


RESULTS_BY_FAMILY: dict[AuditFamily, frozenset[AuditResult]] = {
    AuditFamily.AUTHZ: frozenset({AuditResult.ALLOW, AuditResult.DENY}),
    AuditFamily.ACTION: frozenset({AuditResult.SUCCEEDED, AuditResult.FAILED}),
}


class AuditEvent(SQLModel, table=True):  # type: ignore[call-arg]
    """Who attempted what, against which resource, and how it ended."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_resource", "resource_type", "resource_id", "created_at"),
        Index("ix_audit_events_user", "user_id", "created_at"),
        Index("ix_audit_events_event", "event", "created_at"),
        Index("ix_audit_events_family_result", "family", "result", "created_at"),
        # Plain strings rather than a database enum: adding a resource or an
        # event name must not be a migration on two backends. The two closed
        # vocabularies below are worth constraining, because a typo in either
        # silently removes rows from every filtered query.
        CheckConstraint("family IN ('authz', 'action')", name="ck_audit_events_family"),
        CheckConstraint(
            "result IN ('allow', 'deny', 'succeeded', 'failed')",
            name="ck_audit_events_result",
        ),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    # Server-side so every replica shares one clock: a pod's own clock can drift,
    # and an audit trail ordered by a skewed timestamp misleads the reader.
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    family: str = Field(nullable=False)
    event: str = Field(nullable=False)
    result: str = Field(nullable=False)
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


class AuditEventRead(BaseModel):
    """One audit row as the API returns it."""

    model_config = {"from_attributes": True}

    id: UUIDstr
    created_at: datetime
    family: str
    event: str
    result: str
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


class AuditEventListResponse(BaseModel):
    """A page of audit rows, newest first."""

    entries: list[AuditEventRead]
    total: int
