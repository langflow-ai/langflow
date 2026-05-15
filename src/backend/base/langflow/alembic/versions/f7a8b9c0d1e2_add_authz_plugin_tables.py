"""add authorization plugin tables (casbin_rule, authz_*)

Revision ID: f7a8b9c0d1e2
Revises: mb01b2c3d4e5
Create Date: 2026-05-15

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "mb01b2c3d4e5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

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
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["parent_role_id"], ["authz_role.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("authz_role", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_role_name"), ["name"], unique=True)
            batch_op.create_index(batch_op.f("ix_authz_role_workspace_id"), ["workspace_id"], unique=False)

    if not migration.table_exists("authz_role_assignment", conn):
        op.create_table(
            "authz_role_assignment",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("role_id", sa.Uuid(), nullable=False),
            sa.Column("domain_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("domain_id", sa.Uuid(), nullable=True),
            sa.Column("assigned_at", sa.DateTime(), nullable=False),
            sa.Column("assigned_by", sa.Uuid(), nullable=True),
            sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["role_id"], ["authz_role.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "role_id", "domain_type", "domain_id", name="uq_authz_role_assignment"),
        )
        with op.batch_alter_table("authz_role_assignment", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_role_assignment_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_role_assignment_role_id"), ["role_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_role_assignment_domain_id"), ["domain_id"], unique=False)

    if not migration.table_exists("authz_team", conn):
        op.create_table(
            "authz_team",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("team_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("adom_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("authz_team", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_team_team_name"), ["team_name"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_team_adom_name"), ["adom_name"], unique=True)

    if not migration.table_exists("authz_team_member", conn):
        op.create_table(
            "authz_team_member",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("team_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["authz_team.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("team_id", "user_id", name="uq_authz_team_member"),
        )
        with op.batch_alter_table("authz_team_member", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_team_member_team_id"), ["team_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_team_member_user_id"), ["user_id"], unique=False)

    if not migration.table_exists("authz_share", conn):
        op.create_table(
            "authz_share",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("resource_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("resource_id", sa.Uuid(), nullable=False),
            sa.Column("scope", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("target_id", sa.Uuid(), nullable=True),
            sa.Column("permission_level", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_by", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "resource_type",
                "resource_id",
                "scope",
                "target_id",
                name="uq_authz_share_resource_target",
            ),
        )
        with op.batch_alter_table("authz_share", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_share_resource_type"), ["resource_type"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_share_resource_id"), ["resource_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_share_scope"), ["scope"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_share_target_id"), ["target_id"], unique=False)

    if not migration.table_exists("authz_edit_lock", conn):
        op.create_table(
            "authz_edit_lock",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("holder_user_id", sa.Uuid(), nullable=False),
            sa.Column("acquired_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["holder_user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("authz_edit_lock", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_edit_lock_flow_id"), ["flow_id"], unique=True)

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
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("authz_audit_log", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_authz_audit_log_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_audit_log_action"), ["action"], unique=False)
            batch_op.create_index(batch_op.f("ix_authz_audit_log_timestamp"), ["timestamp"], unique=False)
            batch_op.create_index("ix_authz_audit_log_user_timestamp", ["user_id", "timestamp"], unique=False)
            batch_op.create_index("ix_authz_audit_log_resource", ["resource_type", "resource_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
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
