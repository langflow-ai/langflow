"""Add Keycloak fields to User model

Revision ID: a87d3f2c6e2c
Revises: 66f72f04a1de
Create Date: 2024-03-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a87d3f2c6e2c"
down_revision: Union[str, None] = "66f72f04a1de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if email column exists before adding it
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [column['name'] for column in inspector.get_columns('user')]

    # Add email field to user table if it doesn't exist
    if 'email' not in columns:
        op.add_column("user", sa.Column("email", sa.String(), nullable=True))

    # Add is_keycloak_user field to user table if it doesn't exist
    if 'is_keycloak_user' not in columns:
        op.add_column("user", sa.Column("is_keycloak_user", sa.Boolean(), default=False, nullable=True))

        # Update existing rows to set is_keycloak_user to false
        op.execute('UPDATE "user" SET is_keycloak_user = false')

        # Make is_keycloak_user non-nullable after setting default values
        op.alter_column("user", "is_keycloak_user", nullable=False)


    # Add is_deleted field to user table if it doesn't exist
    if 'is_deleted' not in columns:
        op.add_column("user", sa.Column("is_deleted", sa.Boolean(), default=False, nullable=True))

        # Update existing rows to set is_deleted to false
        op.execute('UPDATE "user" SET is_deleted = false')

        # Make is_deleted non-nullable after setting default values
        op.alter_column("user", "is_deleted", nullable=False)

    # Add deleted_at field to user table if it doesn't exist
    if 'deleted_at' not in columns:
        op.add_column("user", sa.Column("deleted_at", sa.DateTime(), nullable=True))

        # Update existing rows to set deleted_at to NULL
        op.execute('UPDATE "user" SET deleted_at = NULL')


def downgrade() -> None:
    # Check if columns exist before trying to drop them
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [column['name'] for column in inspector.get_columns('user')]

    # Remove the columns if they exist
    if 'is_keycloak_user' in columns:
        op.drop_column("user", "is_keycloak_user")
    if 'email' in columns:
        op.drop_column("user", "email")
    if 'is_deleted' in columns:
        op.drop_column("user", "is_deleted")
    if 'deleted_at' in columns:
        op.drop_column("user", "deleted_at")
