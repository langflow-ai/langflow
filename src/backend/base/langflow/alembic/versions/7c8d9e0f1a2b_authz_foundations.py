"""authz foundations — casbin_rule, authz_* tables, workspace_id columns

Revision ID: 7c8d9e0f1a2b
Revises: mb01b2c3d4e5
Create Date: 2026-05-20

Phase: EXPAND

Single consolidated migration for the OSS authorization layer (PR #13153).
Emits the final schema directly — partial unique indexes that handle NULL
columns, ``DateTime(timezone=True)`` everywhere, CHECK constraints on
``authz_share`` enum-like columns, and the ``workspace_id`` column on flow /
folder / deployment.

This replaces what was previously a chain of six smaller migrations that were
collapsed before any of them shipped:

* ``f7a8b9c0d1e2`` (initial authz tables)
* ``c8e5f4b2a9d7`` (workspace_id columns)
* ``d9e8f7a6b5c4`` (partial unique indexes on authz_role_assignment)
* ``e4f5a6b7c8d9`` (partial unique indexes on authz_share)
* ``f0a1b2c3d4e5`` (timestamps tz-aware, ptype index, FK fix, composite index, widened partial index)
* ``b2c3d4e5f6a1`` (CHECK constraints on authz_share)

Partial unique indexes use ``postgresql_where`` / ``sqlite_where`` — the
project targets PostgreSQL and SQLite only.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

revision: str = "7c8d9e0f1a2b"  # pragma: allowlist secret
down_revision: str | None = "mb01b2c3d4e5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_WORKSPACE_TABLES = ("flow", "folder", "deployment")


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # casbin_rule — Casbin policy storage (SQLAlchemy adapter compatible)
    # ------------------------------------------------------------------
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
        # Casbin's loader filters by ``ptype`` on every load_policy() and
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
                name="scope_enum",
            ),
            sa.CheckConstraint(
                "permission_level IN ('read', 'write', 'execute', 'admin')",
                name="permission_enum",
            ),
            sa.CheckConstraint(
                "(scope IN ('team', 'user') AND target_id IS NOT NULL) "
                "OR (scope IN ('private', 'public') AND target_id IS NULL)",
                name="scope_target_consistency",
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
