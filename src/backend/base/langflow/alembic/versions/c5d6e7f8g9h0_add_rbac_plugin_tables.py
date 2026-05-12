"""add RBAC plugin tables role, user_role, resource_permission, audit_log

Revision ID: c5d6e7f8g9h0
Revises: mb01b2c3d4e5
Create Date: 2026-05-11

Phase: EXPAND
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

revision: str = "c5d6e7f8g9h0"
down_revision: str | None = "mb01b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    
    if not migration.table_exists("role", conn):
        op.create_table(
            "role",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False),
            sa.Column("permissions", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("role", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_role_name"), ["name"], unique=True)
    
    if not migration.table_exists("user_role", conn):
        op.create_table(
            "user_role",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("role_id", sa.Uuid(), nullable=False),
            sa.Column("assigned_at", sa.DateTime(), nullable=False),
            sa.Column("assigned_by", sa.Uuid(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("user_role", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_user_role_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_user_role_role_id"), ["role_id"], unique=False)
            batch_op.create_index(
                batch_op.f("uq_user_role_user_role"),
                ["user_id", "role_id"],
                unique=True,
            )
    
    if not migration.table_exists("resource_permission", conn):
        op.create_table(
            "resource_permission",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("resource_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("resource_id", sa.Uuid(), nullable=False),
            sa.Column("permission", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("granted_at", sa.DateTime(), nullable=False),
            sa.Column("granted_by", sa.Uuid(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["granted_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("resource_permission", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_resource_permission_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_resource_permission_resource_type"), ["resource_type"], unique=False)
            batch_op.create_index(batch_op.f("ix_resource_permission_resource_id"), ["resource_id"], unique=False)
            batch_op.create_index(
                batch_op.f("ix_resource_permission_user_resource"),
                ["user_id", "resource_type", "resource_id"],
                unique=False,
            )
    
    if not migration.table_exists("audit_log", conn):
        op.create_table(
            "audit_log",
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
        with op.batch_alter_table("audit_log", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_audit_log_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_audit_log_action"), ["action"], unique=False)
            batch_op.create_index(batch_op.f("ix_audit_log_timestamp"), ["timestamp"], unique=False)
            batch_op.create_index(
                batch_op.f("ix_audit_log_user_timestamp"),
                ["user_id", "timestamp"],
                unique=False,
            )
            batch_op.create_index(
                batch_op.f("ix_audit_log_resource"),
                ["resource_type", "resource_id"],
                unique=False,
            )


def downgrade() -> None:
    conn = op.get_bind()
    
    if migration.table_exists("audit_log", conn):
        with op.batch_alter_table("audit_log", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_audit_log_resource"))
            batch_op.drop_index(batch_op.f("ix_audit_log_user_timestamp"))
            batch_op.drop_index(batch_op.f("ix_audit_log_timestamp"))
            batch_op.drop_index(batch_op.f("ix_audit_log_action"))
            batch_op.drop_index(batch_op.f("ix_audit_log_user_id"))
        op.drop_table("audit_log")
    
    if migration.table_exists("resource_permission", conn):
        with op.batch_alter_table("resource_permission", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_resource_permission_user_resource"))
            batch_op.drop_index(batch_op.f("ix_resource_permission_resource_id"))
            batch_op.drop_index(batch_op.f("ix_resource_permission_resource_type"))
            batch_op.drop_index(batch_op.f("ix_resource_permission_user_id"))
        op.drop_table("resource_permission")
    
    if migration.table_exists("user_role", conn):
        with op.batch_alter_table("user_role", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("uq_user_role_user_role"))
            batch_op.drop_index(batch_op.f("ix_user_role_role_id"))
            batch_op.drop_index(batch_op.f("ix_user_role_user_id"))
        op.drop_table("user_role")
    
    if migration.table_exists("role", conn):
        with op.batch_alter_table("role", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_role_name"))
        op.drop_table("role")
