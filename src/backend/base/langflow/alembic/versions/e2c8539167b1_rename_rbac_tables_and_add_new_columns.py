"""rename rbac tables and add new columns

Revision ID: e2c8539167b1
Revises: c5d6e7f8g9h0
Create Date: 2026-05-14 11:37:32.663086

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = 'e2c8539167b1'
down_revision: Union[str, None] = 'c5d6e7f8g9h0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Rename tables (preserves data)
    if migration.table_exists("role", conn):
        op.rename_table("role", "rbac_role")
    
    if migration.table_exists("user_role", conn):
        op.rename_table("user_role", "rbac_user_role")
    
    if migration.table_exists("resource_permission", conn):
        op.rename_table("resource_permission", "rbac_resource_permission")
    
    if migration.table_exists("audit_log", conn):
        op.rename_table("audit_log", "rbac_audit_log")
    
    # Add new columns to rbac_role
    if migration.table_exists("rbac_role", conn):
        with op.batch_alter_table("rbac_role", schema=None) as batch_op:
            # Add parent_role_id for role inheritance
            batch_op.add_column(sa.Column("parent_role_id", sa.Uuid(), nullable=True))
            batch_op.create_foreign_key(
                "fk_rbac_role_parent_role_id_rbac_role",
                "rbac_role",
                ["parent_role_id"],
                ["id"],
                ondelete="SET NULL"
            )
            
            # Add workspace_id for future workspace isolation
            batch_op.add_column(sa.Column("workspace_id", sa.Uuid(), nullable=True))
            batch_op.create_index("ix_rbac_role_workspace_id", ["workspace_id"], unique=False)
            
            # Add created_by for audit trail
            batch_op.add_column(sa.Column("created_by", sa.Uuid(), nullable=True))
            batch_op.create_foreign_key(
                "fk_rbac_role_created_by_user",
                "user",
                ["created_by"],
                ["id"],
                ondelete="SET NULL"
            )
    
    # Update rbac_resource_permission: change index to unique constraint
    if migration.table_exists("rbac_resource_permission", conn):
        with op.batch_alter_table("rbac_resource_permission", schema=None) as batch_op:
            # Drop old non-unique index
            batch_op.drop_index("ix_resource_permission_user_resource")
            
            # Create new unique index
            batch_op.create_index(
                "uq_rbac_resource_permission_user_resource_perm",
                ["user_id", "resource_type", "resource_id", "permission"],
                unique=True
            )
    
    # Update foreign key references in rbac_user_role
    if migration.table_exists("rbac_user_role", conn):
        with op.batch_alter_table("rbac_user_role", schema=None) as batch_op:
            # Drop old foreign key to role table
            batch_op.drop_constraint("fk_user_role_role_id_role", type_="foreignkey")
            
            # Create new foreign key to rbac_role table
            batch_op.create_foreign_key(
                "fk_rbac_user_role_role_id_rbac_role",
                "rbac_role",
                ["role_id"],
                ["id"],
                ondelete="CASCADE"
            )


def downgrade() -> None:
    conn = op.get_bind()
    
    # Remove new columns from rbac_role
    if migration.table_exists("rbac_role", conn):
        with op.batch_alter_table("rbac_role", schema=None) as batch_op:
            batch_op.drop_constraint("fk_rbac_role_created_by_user", type_="foreignkey")
            batch_op.drop_column("created_by")
            
            batch_op.drop_index("ix_rbac_role_workspace_id")
            batch_op.drop_column("workspace_id")
            
            batch_op.drop_constraint("fk_rbac_role_parent_role_id_rbac_role", type_="foreignkey")
            batch_op.drop_column("parent_role_id")
    
    # Revert rbac_resource_permission index changes
    if migration.table_exists("rbac_resource_permission", conn):
        with op.batch_alter_table("rbac_resource_permission", schema=None) as batch_op:
            batch_op.drop_index("uq_rbac_resource_permission_user_resource_perm")
            batch_op.create_index(
                "ix_resource_permission_user_resource",
                ["user_id", "resource_type", "resource_id"],
                unique=False
            )
    
    # Revert foreign key in rbac_user_role
    if migration.table_exists("rbac_user_role", conn):
        with op.batch_alter_table("rbac_user_role", schema=None) as batch_op:
            batch_op.drop_constraint("fk_rbac_user_role_role_id_rbac_role", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_user_role_role_id_role",
                "role",
                ["role_id"],
                ["id"],
                ondelete="CASCADE"
            )
    
    # Rename tables back
    if migration.table_exists("rbac_audit_log", conn):
        op.rename_table("rbac_audit_log", "audit_log")
    
    if migration.table_exists("rbac_resource_permission", conn):
        op.rename_table("rbac_resource_permission", "resource_permission")
    
    if migration.table_exists("rbac_user_role", conn):
        op.rename_table("rbac_user_role", "user_role")
    
    if migration.table_exists("rbac_role", conn):
        op.rename_table("rbac_role", "role")

# Made with Bob
