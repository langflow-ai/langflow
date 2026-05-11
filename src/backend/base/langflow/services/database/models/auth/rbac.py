from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import JSON, Column, ForeignKey, Index
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class Role(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "role"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    is_system: bool = Field(default=False)
    permissions: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserRole(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "user_role"
    __table_args__ = (Index("uq_user_role_user_role", "user_id", "role_id", unique=True),)

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    role_id: UUIDstr = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("role.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class ResourcePermission(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "resource_permission"
    __table_args__ = (
        Index("ix_resource_permission_user_resource", "user_id", "resource_type", "resource_id"),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    resource_type: str = Field(index=True)
    resource_id: UUIDstr = Field(index=True)
    permission: str = Field()
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    granted_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class AuditLog(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_user_timestamp", "user_id", "timestamp"),
        Index("ix_audit_log_resource", "resource_type", "resource_id"),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    action: str = Field(index=True)
    resource_type: str | None = Field(default=None)
    resource_id: UUIDstr | None = Field(default=None)
    result: str = Field()
    details: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
