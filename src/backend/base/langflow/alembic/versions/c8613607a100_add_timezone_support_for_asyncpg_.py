"""Add timezone support for asyncpg compatibility

Revision ID: c8613607a100
Revises: 182e5471b900
Create Date: 2025-11-07 14:56:02.303392

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8613607a100"  # pragma: allowlist secret
down_revision: str | None = "182e5471b900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Only apply changes if using PostgreSQL
    # SQLite and other databases don't have timezone-aware datetime types
    if conn.dialect.name == "postgresql":
        # Alter datetime columns to use TIMESTAMP WITH TIME ZONE

        # User table
        op.alter_column(
            "user",
            "create_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=False,
        )
        op.alter_column(
            "user",
            "updated_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=False,
        )
        op.alter_column(
            "user",
            "last_login_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=True,
        )

        # ApiKey table
        op.alter_column(
            "apikey",
            "last_used_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=True,
        )

        # Flow table
        op.alter_column(
            "flow",
            "updated_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=True,
        )

        # Message table
        op.alter_column(
            "message",
            "timestamp",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=False,
        )

        # File table
        op.alter_column(
            "file",
            "created_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=False,
        )
        op.alter_column(
            "file",
            "updated_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=False,
        )

        # Transaction table
        op.alter_column(
            "transaction",
            "timestamp",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=False,
        )

        # VertexBuild table
        op.alter_column(
            "vertex_build",
            "timestamp",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(timezone=False),
            existing_nullable=False,
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Only apply changes if using PostgreSQL
    if conn.dialect.name == "postgresql":
        # Revert datetime columns to TIMESTAMP WITHOUT TIME ZONE

        # User table
        op.alter_column(
            "user",
            "create_at",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
        op.alter_column(
            "user",
            "updated_at",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
        op.alter_column(
            "user",
            "last_login_at",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

        # ApiKey table
        op.alter_column(
            "apikey",
            "last_used_at",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

        # Flow table
        op.alter_column(
            "flow",
            "updated_at",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

        # Message table
        op.alter_column(
            "message",
            "timestamp",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )

        # File table
        op.alter_column(
            "file",
            "created_at",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
        op.alter_column(
            "file",
            "updated_at",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )

        # Transaction table
        op.alter_column(
            "transaction",
            "timestamp",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )

        # VertexBuild table
        op.alter_column(
            "vertex_build",
            "timestamp",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
