"""Add Keycloak fields to User model

Revision ID: a87d3f2c6e2c
Revises: dd9e0804ebd1
Create Date: 2024-03-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a87d3f2c6e2c"
down_revision: Union[str, None] = "dd9e0804ebd1"
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
