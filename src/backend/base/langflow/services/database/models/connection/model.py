"""Database tables for connection metadata and encrypted token material."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - SQLModel resolves annotations at runtime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlmodel import JSON, Column, DateTime, Field, SQLModel, func

from langflow.schema.serialize import UUIDstr  # noqa: TC001 - SQLModel resolves annotations at runtime
from langflow.services.database.models.connection.schemas import (
    ConnectionHealth,
    ConnectionOwnershipMode,
    PersistedConnectionStatus,
)


class ConnectionBase(SQLModel):
    provider_key: str = Field(max_length=120)
    name: str = Field(max_length=64)
    display_name: str = Field(max_length=255)
    ownership_mode: str = Field(default=ConnectionOwnershipMode.USER.value, max_length=16)
    status: str = Field(default=PersistedConnectionStatus.PENDING.value, max_length=16)
    health: str = Field(default=ConnectionHealth.UNKNOWN.value, max_length=16)
    granted_scopes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    executing_identity: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    allow_non_interactive: bool = Field(default=False, nullable=False)


class Connection(ConnectionBase, table=True):  # type: ignore[call-arg]
    """Non-secret connection metadata."""

    __tablename__ = "connection"
    __table_args__ = (
        CheckConstraint(
            "(ownership_mode = 'user' AND owner_id IS NOT NULL) OR (ownership_mode = 'instance' AND owner_id IS NULL)",
            name="ck_connection_owner_mode",
        ),
        CheckConstraint(
            "status IN ('pending', 'ready', 'expired', 'revoked', 'error')",
            name="ck_connection_status",
        ),
        CheckConstraint(
            "health IN ('unknown', 'healthy', 'unhealthy')",
            name="ck_connection_health",
        ),
        Index(
            "uq_connection_user_provider_name",
            "owner_id",
            "provider_key",
            "name",
            unique=True,
            sqlite_where=sa.text("ownership_mode = 'user'"),
            postgresql_where=sa.text("ownership_mode = 'user'"),
        ),
        Index(
            "uq_connection_instance_provider_name",
            "provider_key",
            "name",
            unique=True,
            sqlite_where=sa.text("ownership_mode = 'instance'"),
            postgresql_where=sa.text("ownership_mode = 'instance'"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    health_checked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class ConnectionSecret(SQLModel, table=True):  # type: ignore[call-arg]
    """Encrypted connection credential envelope, isolated from metadata reads."""

    __tablename__ = "connection_secret"

    connection_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("connection.id", ondelete="CASCADE"), nullable=False, primary_key=True),
    )
    encrypted_payload: str = Field(sa_column=Column(sa.Text(), nullable=False))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
