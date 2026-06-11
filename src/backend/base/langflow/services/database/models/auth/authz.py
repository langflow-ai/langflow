"""Authorization (RBAC) tables (Alembic-owned; plugins populate policy data)."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, UniqueConstraint, text
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


def _tz_aware_now() -> datetime:
    """Return a TZ-aware UTC datetime — used by every authz default_factory."""
    return datetime.now(timezone.utc)


def _tz_column(*, nullable: bool = False, index: bool = False) -> Column:
    """Return a ``DateTime(timezone=True)`` column — keeps the type consistent."""
    return Column(sa.DateTime(timezone=True), nullable=nullable, index=index)


class CasbinRule(SQLModel, table=True):  # type: ignore[call-arg]
    """Policy rule storage (ptype-indexed for loader queries)."""

    __tablename__ = "casbin_rule"
    __table_args__ = (Index("ix_casbin_rule_ptype", "ptype"),)

    id: int | None = Field(default=None, primary_key=True)
    ptype: str = Field(max_length=255)
    v0: str | None = Field(default=None, max_length=255)
    v1: str | None = Field(default=None, max_length=255)
    v2: str | None = Field(default=None, max_length=255)
    v3: str | None = Field(default=None, max_length=255)
    v4: str | None = Field(default=None, max_length=255)
    v5: str | None = Field(default=None, max_length=255)


class AuthzRole(SQLModel, table=True):  # type: ignore[call-arg]
    """Role metadata for admin UI."""

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
    created_at: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column())
    updated_at: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column())
    created_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )


class AuthzRoleAssignment(SQLModel, table=True):  # type: ignore[call-arg]
    """Binds a user to a role within an optional domain (global/org/workspace).

    A plain UNIQUE(user_id, role_id, domain_type, domain_id) treats NULL
    ``domain_id`` values as never-equal, so duplicates with NULL would slip
    through. Two partial unique indexes cover the cases without gaps:

    * scoped: rows with ``domain_id IS NOT NULL`` (workspace/org assignments).
    * unscoped: rows with ``domain_id IS NULL`` (every domain_type — global,
      and any ill-formed org/workspace without an id — so the unique guarantee
      is exhaustive regardless of how callers spell ``domain_type``).
    """

    __tablename__ = "authz_role_assignment"
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
            "uq_authz_role_assignment_unscoped",
            "user_id",
            "role_id",
            "domain_type",
            unique=True,
            postgresql_where=text("domain_id IS NULL"),
            sqlite_where=text("domain_id IS NULL"),
        ),
        # Hot-path lookup: "all assignments for user X scoped to a domain"
        # Composite index for enforce() lookups.
        # single-column scans.
        Index(
            "ix_authz_role_assignment_user_domain",
            "user_id",
            "domain_type",
            "domain_id",
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
    # Explicit ``sa_column`` so SQLModel emits ``sa.Uuid()`` matching the
    # migration's column type. Without this, SQLModel can fall back to
    # ``AutoString``/``CHAR(32)`` on SQLite, which drifts from the migration
    # and confuses downstream type introspection.
    domain_id: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), nullable=True, index=True),
    )
    assigned_at: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column())
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
    created_at: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column())
    updated_at: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column())


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
    created_at: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column())


class AuthzShare(SQLModel, table=True):  # type: ignore[call-arg]
    """Resource share record granting access at a specific scope/permission level.

    ``target_id`` is naturally NULL for PRIVATE/PUBLIC scopes and a UUID for
    TEAM/USER scopes — partial unique indexes split the two cases so the NULL
    rows can still be deduplicated.

    ``created_by`` uses ``SET NULL`` (not CASCADE) so deleting a user does not
    silently revoke every share that user ever created. The grant survives
    with no recorded creator; admins can clean up if needed.
    """

    __tablename__ = "authz_share"
    __table_args__ = (
        # Hot path: "list all shares for resource X" → composite index avoids
        # a bitmap-AND of two single-column indexes.
        Index("ix_authz_share_resource", "resource_type", "resource_id"),
        # Bound scope and permission_level to known enum values at the DB
        # Without this, a plugin (or manual INSERT) could
        # write a typo like ``scope='PRIVATE'`` that silently bypasses the
        # partial unique indexes (which match on the lowercase form).
        CheckConstraint(
            "scope IN ('private', 'team', 'user', 'public')",
            name="ck_authz_share_scope_enum",
        ),
        CheckConstraint(
            "permission_level IN ('read', 'write', 'execute', 'admin')",
            name="ck_authz_share_permission_enum",
        ),
        # Targeted (TEAM/USER) shares require a target_id; untargeted
        # (PRIVATE/PUBLIC) shares forbid one. Matches the partial-unique-index
        # split so callers can't accidentally construct rows that one index
        # covers but the other shouldn't.
        CheckConstraint(
            "(scope IN ('team', 'user') AND target_id IS NOT NULL) "
            "OR (scope IN ('private', 'public') AND target_id IS NULL)",
            name="ck_authz_share_scope_target_consistency",
        ),
        Index(
            "uq_authz_share_targeted",
            "resource_type",
            "resource_id",
            "scope",
            "target_id",
            unique=True,
            postgresql_where=text("target_id IS NOT NULL"),
            sqlite_where=text("target_id IS NOT NULL"),
        ),
        Index(
            "uq_authz_share_untargeted",
            "resource_type",
            "resource_id",
            "scope",
            unique=True,
            postgresql_where=text("target_id IS NULL"),
            sqlite_where=text("target_id IS NULL"),
        ),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    resource_type: str = Field(index=True)
    resource_id: UUIDstr = Field(index=True)
    scope: str = Field(index=True)
    target_id: UUIDstr | None = Field(default=None, index=True)
    permission_level: str = Field(default=SharePermissionLevel.READ.value)
    created_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    created_at: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column())


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
    acquired_at: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column())
    # ``index=True`` matches the migration's ``ix_authz_edit_lock_expires_at``
    # so the expired-lock sweeper can do an index seek instead of a table scan.
    expires_at: datetime = Field(sa_column=_tz_column(index=True))


# TODO: AuthzAuditLog is append-only and unbounded. At large scale this
# table will outgrow practical query windows. Decide between (a) Postgres native
# partitioning by ``timestamp`` (monthly/quarterly), (b) an out-of-band
# archival/TTL job, or (c) SIEM export per design note §5.3 Phase 5. The
# composite ix_authz_audit_log_user_timestamp index keeps "all events for user
# X in last N days" fast under either strategy.
class AuthzAuditLog(SQLModel, table=True):  # type: ignore[call-arg]
    """Append-only audit row produced by every authorization decision."""

    __tablename__ = "authz_audit_log"
    __table_args__ = (
        Index("ix_authz_audit_log_user_timestamp", "user_id", "timestamp"),
        Index("ix_authz_audit_log_resource", "resource_type", "resource_id"),
        # ``owner_override`` is the third value the framework writes (see
        # ``_AUDIT_OWNER_OVERRIDE`` in services/authorization/utils.py); it
        # must be in the CHECK set or owner-shortcut audit rows would
        # silently fail the constraint.
        CheckConstraint(
            "result IN ('allow', 'deny', 'owner_override')",
            name="ck_authz_audit_log_result_enum",
        ),
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
    timestamp: datetime = Field(default_factory=_tz_aware_now, sa_column=_tz_column(index=True))
