"""Authz foundations: tables, workspace_id columns, and built-in system roles.

Phase: EXPAND
Revision ID: 7c8d9e0f1a2b
Revises: f6b3ce6845d4
Create Date: 2026-05-20

This migration is purely additive (new tables + nullable ``workspace_id``
columns on flow/folder/deployment) and follows the expand-contract pattern
under the EXPAND phase: no destructive operations on existing schema.

Downgrade is intentionally lossy: every authz_* row, every casbin_rule, and
every authz_share / authz_audit_log entry is dropped. Operators running
``alembic downgrade`` past this revision will lose all RBAC policy and audit
state. There is no in-place rollback path for enterprise deployments — back
up the authz tables before downgrading if you intend to roll forward again.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "7c8d9e0f1a2b"  # pragma: allowlist secret
down_revision: str | None = "f6b3ce6845d4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_WORKSPACE_TABLES = ("flow", "folder", "deployment")

_VIEWER_PERMISSIONS: tuple[str, ...] = (
    "flow:read",
    "flow:execute",
    "deployment:read",
    "project:read",
    "knowledge_base:read",
    "variable:read",
    "file:read",
)

_DEVELOPER_EXTRA: tuple[str, ...] = (
    "flow:write",
    "flow:create",
    "deployment:write",
    "deployment:create",
    "deployment:execute",
    "project:write",
    "project:create",
    "knowledge_base:write",
    "knowledge_base:create",
    "knowledge_base:ingest",
    "variable:write",
    "variable:create",
    "file:write",
    "file:create",
)

_ADMIN_EXTRA: tuple[str, ...] = (
    "flow:delete",
    "flow:deploy",
    "deployment:delete",
    # ``deploy`` is a flow-only action (FlowAction.DEPLOY). DeploymentAction
    # has only read/write/create/delete/execute, so a ``deployment:deploy``
    # row would never match an enforce() call — exclude it from the seed
    # rather than ship a canonical slug nothing can use.
    "project:delete",
    "knowledge_base:delete",
    "variable:delete",
    "file:delete",
    "share:read",
    "share:create",
    "share:update",
    "share:delete",
)

_SYSTEM_ROLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "viewer",
        "Read-only access to flows, deployments, projects, and supporting resources.",
        _VIEWER_PERMISSIONS,
    ),
    (
        "developer",
        "Author and execute flows; manage variables, knowledge bases, and files.",
        _VIEWER_PERMISSIONS + _DEVELOPER_EXTRA,
    ),
    (
        "admin",
        "Full management of resources and shares within the workspace.",
        _VIEWER_PERMISSIONS + _DEVELOPER_EXTRA + _ADMIN_EXTRA,
    ),
)


def _seed_system_roles(conn: sa.Connection) -> None:
    """Insert viewer / developer / admin roles (idempotent)."""
    authz_role = sa.table(
        "authz_role",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_system", sa.Boolean()),
        sa.column("permissions", sa.JSON()),
        sa.column("parent_role_id", sa.Uuid()),
        sa.column("workspace_id", sa.Uuid()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.Uuid()),
    )

    timestamp = datetime.now(timezone.utc)
    dialect = conn.dialect.name
    for name, description, permissions in _SYSTEM_ROLES:
        values = {
            "id": uuid4(),
            "name": name,
            "description": description,
            "is_system": True,
            "permissions": list(permissions),
            "parent_role_id": None,
            "workspace_id": None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "created_by": None,
        }
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(authz_role).values(**values).on_conflict_do_nothing(index_elements=["name"])
            conn.execute(stmt)
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            stmt = sqlite_insert(authz_role).values(**values).on_conflict_do_nothing(index_elements=["name"])
            conn.execute(stmt)
        else:
            already_present = conn.execute(
                sa.select(sa.literal(1)).select_from(authz_role).where(authz_role.c.name == name)
            ).scalar()
            if already_present:
                continue
            # Why: SELECT-then-INSERT is racy on dialects without
            # ``on_conflict_do_nothing``. Two concurrent migration runners can
            # both observe ``already_present=False`` and both INSERT, losing
            # the second one to the unique-constraint. Wrap in a SAVEPOINT and
            # swallow IntegrityError so the migration stays idempotent under
            # concurrent first-deploys. See PR #13153 review item R5.
            from sqlalchemy.exc import IntegrityError

            try:
                with conn.begin_nested():
                    conn.execute(authz_role.insert().values(**values))
            except IntegrityError:
                continue


def upgrade() -> None:
    conn = op.get_bind()

    # policy rules table
    if not migration.table_exists("casbin_rule", conn):
        op.create_table(
            "casbin_rule",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("ptype", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
            sa.Column("v0", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
            sa.Column("v1", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
            sa.Column("v2", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
            sa.Column("v3", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
            sa.Column("v4", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
            sa.Column("v5", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        # The policy loader's loader filters by ``ptype`` on every load_policy() and
        # AddPolicy() — required for non-trivial policy volumes.
        op.create_index("ix_casbin_rule_ptype", "casbin_rule", ["ptype"])

    # ------------------------------------------------------------------
    # authz_role — role metadata for the admin UI
    # ------------------------------------------------------------------
    if not migration.table_exists("authz_role", conn):
        op.create_table(
            "authz_role",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False),
            sa.Column("permissions", sa.JSON(), nullable=False),
            sa.Column("parent_role_id", sa.Uuid(), nullable=True),
            sa.Column("workspace_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.ForeignKeyConstraint(["parent_role_id"], ["authz_role.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("authz_role", schema=None) as batch_op:
            # ``name: str = Field(index=True, unique=True)`` becomes a single
            # unique index in SQLModel's metadata; mirror that exactly so the
            # model/migration consistency check stays clean.
            batch_op.create_index(batch_op.f("ix_authz_role_name"), ["name"], unique=True)
            batch_op.create_index(batch_op.f("ix_authz_role_workspace_id"), ["workspace_id"], unique=False)

    # ------------------------------------------------------------------
    # authz_role_assignment — partial unique indexes handle NULL domain_id
    # ------------------------------------------------------------------
    if not migration.table_exists("authz_role_assignment", conn):
        op.create_table(
            "authz_role_assignment",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("role_id", sa.Uuid(), nullable=False),
            sa.Column("domain_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("domain_id", sa.Uuid(), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("assigned_by", sa.Uuid(), nullable=True),
            sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["role_id"], ["authz_role.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("authz_role_assignment", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_role_assignment_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_role_assignment_role_id"), ["role_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_role_assignment_domain_id"), ["domain_id"], unique=False)

        # Hot-path lookup index: "all assignments for user X scoped to domain
        # (type, id)" — the canonical query an authorization plugin issues on
        # every request to compute effective roles. Single-column indexes
        # leave the planner with a choice between two non-covering scans;
        # this composite gives a single index seek.
        op.create_index(
            "ix_authz_role_assignment_user_domain",
            "authz_role_assignment",
            ["user_id", "domain_type", "domain_id"],
            unique=False,
        )

        # Partial unique indexes — NULL domain_id is never-equal in SQL, so
        # split the constraint into scoped and unscoped buckets. The unscoped
        # bucket filters on domain_id IS NULL only (NOT also on
        # domain_type = 'global') so ill-formed rows like
        # ("user", "role", "org", NULL) are still deduplicated.
        op.create_index(
            "uq_authz_role_assignment_scoped",
            "authz_role_assignment",
            ["user_id", "role_id", "domain_type", "domain_id"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NOT NULL"),
            sqlite_where=sa.text("domain_id IS NOT NULL"),
        )
        op.create_index(
            "uq_authz_role_assignment_unscoped",
            "authz_role_assignment",
            ["user_id", "role_id", "domain_type"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NULL"),
            sqlite_where=sa.text("domain_id IS NULL"),
        )

    # ------------------------------------------------------------------
    # authz_team — logical user grouping
    # ------------------------------------------------------------------
    if not migration.table_exists("authz_team", conn):
        op.create_table(
            "authz_team",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("team_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("adom_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("authz_team", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_team_team_name"), ["team_name"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_team_adom_name"), ["adom_name"], unique=True)

    # ------------------------------------------------------------------
    # authz_team_member
    # ------------------------------------------------------------------
    if not migration.table_exists("authz_team_member", conn):
        op.create_table(
            "authz_team_member",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("team_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["authz_team.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("team_id", "user_id", name="uq_authz_team_member"),
        )
        with op.batch_alter_table("authz_team_member", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_team_member_team_id"), ["team_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_team_member_user_id"), ["user_id"], unique=False)

    # ------------------------------------------------------------------
    # authz_share — per-resource grants with partial unique indexes + CHECKs
    # ------------------------------------------------------------------
    if not migration.table_exists("authz_share", conn):
        op.create_table(
            "authz_share",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("resource_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("resource_id", sa.Uuid(), nullable=False),
            sa.Column("scope", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("target_id", sa.Uuid(), nullable=True),
            sa.Column("permission_level", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "scope IN ('private', 'team', 'user', 'public')",
                name="ck_authz_share_scope_enum",
            ),
            sa.CheckConstraint(
                "permission_level IN ('read', 'write', 'execute', 'admin')",
                name="ck_authz_share_permission_enum",
            ),
            sa.CheckConstraint(
                "(scope IN ('team', 'user') AND target_id IS NOT NULL) "
                "OR (scope IN ('private', 'public') AND target_id IS NULL)",
                name="ck_authz_share_scope_target_consistency",
            ),
        )
        with op.batch_alter_table("authz_share", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_share_resource_type"), ["resource_type"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_share_resource_id"), ["resource_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_share_scope"), ["scope"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_share_target_id"), ["target_id"], unique=False)

        # Composite covering index for "list all shares for resource X".
        op.create_index("ix_authz_share_resource", "authz_share", ["resource_type", "resource_id"])
        # Partial unique indexes split the NULL/non-NULL target_id cases.
        op.create_index(
            "uq_authz_share_targeted",
            "authz_share",
            ["resource_type", "resource_id", "scope", "target_id"],
            unique=True,
            postgresql_where=sa.text("target_id IS NOT NULL"),
            sqlite_where=sa.text("target_id IS NOT NULL"),
        )
        op.create_index(
            "uq_authz_share_untargeted",
            "authz_share",
            ["resource_type", "resource_id", "scope"],
            unique=True,
            postgresql_where=sa.text("target_id IS NULL"),
            sqlite_where=sa.text("target_id IS NULL"),
        )

    # ------------------------------------------------------------------
    # authz_edit_lock — optimistic edit lock per flow
    # ------------------------------------------------------------------
    if not migration.table_exists("authz_edit_lock", conn):
        op.create_table(
            "authz_edit_lock",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("holder_user_id", sa.Uuid(), nullable=False),
            sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["holder_user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("authz_edit_lock", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_edit_lock_flow_id"), ["flow_id"], unique=True)
            # Expired-lock sweeper queries WHERE expires_at < now() — without
            # this index that's a full table scan. Cheaper to add here than
            # to retrofit once a cleanup job lands and starts hurting.
            batch_op.create_index(
                batch_op.f("ix_authz_edit_lock_expires_at"),
                ["expires_at"],
                unique=False,
            )

    # ------------------------------------------------------------------
    # authz_audit_log — append-only authorization audit
    # ------------------------------------------------------------------
    if not migration.table_exists("authz_audit_log", conn):
        op.create_table(
            "authz_audit_log",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=True),
            sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("resource_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("resource_id", sa.Uuid(), nullable=True),
            sa.Column("result", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            # ``owner_override`` is the third value the framework writes
            # (see ``_AUDIT_OWNER_OVERRIDE`` in
            # ``services/authorization/utils.py``) — without it in the CHECK
            # set, an authorization plugin's owner-shortcircuit audit row would
            # silently violate the constraint.
            sa.CheckConstraint(
                "result IN ('allow', 'deny', 'owner_override')",
                name="ck_authz_audit_log_result_enum",
            ),
        )
        with op.batch_alter_table("authz_audit_log", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_audit_log_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_audit_log_action"), ["action"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_audit_log_timestamp"), ["timestamp"], unique=False)

        op.create_index("ix_authz_audit_log_user_timestamp", "authz_audit_log", ["user_id", "timestamp"])
        op.create_index("ix_authz_audit_log_resource", "authz_audit_log", ["resource_type", "resource_id"])

    # ------------------------------------------------------------------
    # workspace_id columns on flow / folder / deployment
    # ------------------------------------------------------------------
    for table in _WORKSPACE_TABLES:
        if not migration.table_exists(table, conn):
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            if not migration.column_exists(table_name=table, column_name="workspace_id", conn=conn):
                batch_op.add_column(sa.Column("workspace_id", sa.Uuid(), nullable=True))
                batch_op.create_index(f"ix_{table}_workspace_id", ["workspace_id"], unique=False)

    if migration.table_exists("authz_role", conn):
        _seed_system_roles(conn)


def downgrade() -> None:
    conn = op.get_bind()

    # workspace_id columns
    for table in _WORKSPACE_TABLES:
        if not migration.table_exists(table, conn):
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            if migration.column_exists(table_name=table, column_name="workspace_id", conn=conn):
                batch_op.drop_index(f"ix_{table}_workspace_id")
                batch_op.drop_column("workspace_id")

    # Tables in reverse-creation order so FKs can drop cleanly.
    for table in (
        "authz_audit_log",
        "authz_edit_lock",
        "authz_share",
        "authz_team_member",
        "authz_team",
        "authz_role_assignment",
        "authz_role",
        "casbin_rule",
    ):
        if migration.table_exists(table, conn):
            op.drop_table(table)
