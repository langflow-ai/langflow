"""Add timezone support for asyncpg compatibility.

Revision ID: c8613607a100
Revises: 182e5471b900
Create Date: 2025-11-07 14:56:02.303392

This migration converts timestamp columns to timestamptz (TIMESTAMP WITH TIME ZONE)
for PostgreSQL to ensure compatibility with asyncpg driver, which requires explicit
timezone handling.

IMPORTANT: Uses AT TIME ZONE 'UTC' to safely convert existing data, assuming all
timestamps were stored as UTC values.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8613607a100"  # pragma: allowlist secret
down_revision: str | None = "182e5471b900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Column definitions: (table_name, column_name, nullable)
DATETIME_COLUMNS: list[tuple[str, str, bool]] = [
    ("user", "create_at", False),
    ("user", "updated_at", False),
    ("user", "last_login_at", True),
    ("apikey", "last_used_at", True),
    ("flow", "updated_at", True),
    ("message", "timestamp", False),
    ("file", "created_at", False),
    ("file", "updated_at", False),
    ("transaction", "timestamp", False),
    ("vertex_build", "timestamp", False),
]


def _convert_to_timestamptz(table: str, column: str, *, nullable: bool) -> None:
    """Convert a timestamp column to timestamptz, interpreting existing data as UTC."""
    op.alter_column(
        table,
        column,
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=nullable,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def _convert_to_timestamp(table: str, column: str, *, nullable: bool) -> None:
    """Convert a timestamptz column back to timestamp, extracting UTC time."""
    op.alter_column(
        table,
        column,
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=nullable,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def upgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name != "postgresql":
        return

    for table, column, nullable in DATETIME_COLUMNS:
        _convert_to_timestamptz(table, column, nullable=nullable)


def downgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name != "postgresql":
        return

    for table, column, nullable in DATETIME_COLUMNS:
        _convert_to_timestamp(table, column, nullable=nullable)
