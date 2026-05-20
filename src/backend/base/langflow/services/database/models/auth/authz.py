"""Authorization (RBAC) plugin tables.

Tables are owned by Langflow OSS (Alembic migrations). Enterprise plugins populate
policy data and may use the Casbin SQLAlchemy adapter against ``casbin_rule``.
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Column, ForeignKey, Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class ShareScope(str, Enum):
    """Audience of an AuthzShare row (private = owner only, public = anyone)."""

    PRIVATE = "private"
    TEAM = "team"
    USER = "user"
    PUBLIC = "public"


class SharePermissionLevel(str, Enum):
    """Level of access granted by an AuthzShare row."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class CasbinRule(SQLModel, table=True):  # type: ignore[call-arg]
    """Casbin policy storage (SQLAlchemy adapter compatible)."""

    __tablename__ = "casbin_rule"

    id: int | None = Field(default=None, primary_key=True)
    ptype: str = Field(max_length=255)
    v0: str | None = Field(default=None, max_length=255)
    v1: str | None = Field(default=None, max_length=255)
    v2: str | None = Field(default=None, max_length=255)
    v3: str | None = Field(default=None, max_length=255)
    v4: str | None = Field(default=None, max_length=255)
    v5: str | None = Field(default=None, max_length=255)


class AuthzRole(SQLModel, table=True):  # type: ignore[call-arg]
    """Role metadata for admin UI; enforceable policies live in ``casbin_rule``."""

    __tablename__ = "authz_role"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str | None = Field(default=None)
    is_system: bool = Field(default=False)
    permissions: list[str] = Field(default_factory=list, sa_column=Column(sa.JSON, nullable=False))
    parent_role_id: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("authz_role.id", ondelete="SET NULL"), nullable=True),
    )
    workspace_id: UUIDstr | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )


class AuthzRoleAssignment(SQLModel, table=True):  # type: ignore[call-arg]
    """Binds a user to a role within an optional domain (global/org/workspace)."""

    __tablename__ = "authz_role_assignment"
    # A plain UNIQUE(user_id, role_id, domain_type, domain_id) treats NULL
    # domain_ids as never-equal, so duplicate global assignments slip through.
    # Use two partial unique indexes instead: one for non-global rows keyed
    # on domain_id, and one for global rows keyed only on (user_id, role_id,
    # domain_type). Postgres and SQLite both support partial indexes.
    __table_args__ = (
        Index(
            "uq_authz_role_assignment_scoped",
            "user_id",
            "role_id",
            "domain_type",
            "domain_id",
            unique=True,
            postgresql_where=text("domain_id IS NOT NULL"),
            sqlite_where=text("domain_id IS NOT NULL"),
        ),
        Index(
            "uq_authz_role_assignment_global",
            "user_id",
            "role_id",
            "domain_type",
            unique=True,
            postgresql_where=text("domain_type = 'global' AND domain_id IS NULL"),
            sqlite_where=text("domain_type = 'global' AND domain_id IS NULL"),
        ),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    role_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("authz_role.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    domain_type: str = Field(default="global", description="global, org, workspace")
    domain_id: UUIDstr | None = Field(default=None, index=True)
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )


class AuthzTeam(SQLModel, table=True):  # type: ignore[call-arg]
    """Logical grouping of users for share scopes and bulk role assignments."""

    __tablename__ = "authz_team"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    team_name: str = Field(index=True)
    adom_name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthzTeamMember(SQLModel, table=True):  # type: ignore[call-arg]
    """Membership row linking a user to an AuthzTeam."""

    __tablename__ = "authz_team_member"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_authz_team_member"),)

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    team_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("authz_team.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    user_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    source: str = Field(default="manual", description="sso or manual")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthzShare(SQLModel, table=True):  # type: ignore[call-arg]
    """Resource share record granting access at a specific scope/permission level."""

    __tablename__ = "authz_share"
    __table_args__ = (
        UniqueConstraint(
            "resource_type",
            "resource_id",
            "scope",
            "target_id",
            name="uq_authz_share_resource_target",
        ),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    resource_type: str = Field(index=True)
    resource_id: UUIDstr = Field(index=True)
    scope: str = Field(index=True)
    target_id: UUIDstr | None = Field(default=None, index=True)
    permission_level: str = Field(default=SharePermissionLevel.READ.value)
    created_by: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthzEditLock(SQLModel, table=True):  # type: ignore[call-arg]
    """Optimistic edit lock that prevents concurrent edits to the same flow."""

    __tablename__ = "authz_edit_lock"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("flow.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
    )
    holder_user_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    )
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field()


class AuthzAuditLog(SQLModel, table=True):  # type: ignore[call-arg]
    """Append-only audit row produced by every authorization decision."""

    __tablename__ = "authz_audit_log"
    __table_args__ = (
        Index("ix_authz_audit_log_user_timestamp", "user_id", "timestamp"),
        Index("ix_authz_audit_log_resource", "resource_type", "resource_id"),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    action: str = Field(index=True)
    resource_type: str | None = Field(default=None)
    resource_id: UUIDstr | None = Field(default=None)
    result: str = Field()
    details: dict | None = Field(default=None, sa_column=Column(sa.JSON))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
