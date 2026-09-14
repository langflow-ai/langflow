"""One append-only row per audited operation against a resource.

The row is a bounded description of an operation, never a copy of resource
state. Nothing here names a flow or a project: a new resource is a new
``resource_type`` value with its own ``details`` schema, never a migration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, Index
from sqlmodel import Field, SQLModel

RESOURCE_TYPE_MAX_LENGTH = 64
RESOURCE_NAME_MAX_LENGTH = 255
ACTOR_TYPE_MAX_LENGTH = 32
ACTING_ISSUER_MAX_LENGTH = 2048
ACTING_SUBJECT_MAX_LENGTH = 512
ACTION_MAX_LENGTH = 128
OPERATION_MAX_LENGTH = 64
EVENT_TYPE_MAX_LENGTH = 16
RESULT_MAX_LENGTH = 16
ERROR_CODE_MAX_LENGTH = 64

# Action, operation and error code evolve; a CHECK over them would make every new value a migration.
EVENT_TYPE_RESULT_CHECK = (
    "(event_type = 'authz' AND result IN ('allow', 'deny')) "
    "OR (event_type = 'action' AND result IN ('succeeded', 'failed'))"
)
ACTING_PAIR_CHECK = (
    "(acting_issuer IS NULL AND acting_subject IS NULL) OR (acting_issuer IS NOT NULL AND acting_subject IS NOT NULL)"
)


class AuditEvent(SQLModel, table=True):  # type: ignore[call-arg]
    """Who attempted which operation on which resource, and how it ended."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(EVENT_TYPE_RESULT_CHECK, name="ck_audit_events_event_type_result"),
        CheckConstraint(ACTING_PAIR_CHECK, name="ck_audit_events_acting_pair"),
        # Ascending keys serve (timestamp DESC, id DESC) by backward scan; DESC keys churn autogenerate.
        Index("ix_audit_events_resource_timeline", "resource_type", "resource_id", "timestamp", "id"),
        Index("ix_audit_events_type_timeline", "resource_type", "timestamp", "id"),
        Index("ix_audit_events_user_timeline", "user_id", "timestamp"),
        Index("ix_audit_events_actor_timeline", "actor_type", "actor_id", "timestamp"),
        Index("ix_audit_events_acting_timeline", "acting_issuer", "acting_subject", "timestamp"),
        Index("ix_audit_events_request_id", "request_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    resource_type: str = Field(sa_column=Column(sa.String(RESOURCE_TYPE_MAX_LENGTH), nullable=False))
    # No foreign keys: an event must outlive the resource, account and credential it names.
    resource_id: UUID = Field(sa_column=Column(sa.Uuid(), nullable=False))
    resource_name: str | None = Field(
        default=None, sa_column=Column(sa.String(RESOURCE_NAME_MAX_LENGTH), nullable=True)
    )
    user_id: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    actor_type: str = Field(sa_column=Column(sa.String(ACTOR_TYPE_MAX_LENGTH), nullable=False))
    actor_id: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    acting_issuer: str | None = Field(
        default=None, sa_column=Column(sa.String(ACTING_ISSUER_MAX_LENGTH), nullable=True)
    )
    acting_subject: str | None = Field(
        default=None, sa_column=Column(sa.String(ACTING_SUBJECT_MAX_LENGTH), nullable=True)
    )
    action: str = Field(sa_column=Column(sa.String(ACTION_MAX_LENGTH), nullable=False))
    operation: str = Field(sa_column=Column(sa.String(OPERATION_MAX_LENGTH), nullable=False))
    event_type: str = Field(sa_column=Column(sa.String(EVENT_TYPE_MAX_LENGTH), nullable=False))
    result: str = Field(sa_column=Column(sa.String(RESULT_MAX_LENGTH), nullable=False))
    error_code: str | None = Field(default=None, sa_column=Column(sa.String(ERROR_CODE_MAX_LENGTH), nullable=True))
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(sa.DateTime(timezone=True), nullable=False),
    )
    request_id: UUID = Field(sa_column=Column(sa.Uuid(), nullable=False))
    details: dict[str, Any] = Field(sa_column=Column(sa.JSON(), nullable=False))


def as_utc(value: datetime) -> datetime:
    """Read a stored timestamp as UTC on every backend.

    SQLite hands the column back without a timezone and PostgreSQL with one; the
    same event must not read differently depending on where it was stored.
    """
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
