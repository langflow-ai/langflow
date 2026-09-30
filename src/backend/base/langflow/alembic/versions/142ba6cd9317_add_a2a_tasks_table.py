"""add a2a_tasks table for durable A2A protocol task storage.

Revision ID: 142ba6cd9317
Revises: 9f1d1d602aa3
Create Date: 2026-06-25 16:52:08.066539

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "142ba6cd9317"  # pragma: allowlist secret
down_revision: str | None = "9f1d1d602aa3"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("a2a_tasks", conn):
        op.create_table(
            "a2a_tasks",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("owner", sa.String(), nullable=False),
            sa.Column("task", _JSON, nullable=False),
            sa.PrimaryKeyConstraint("id", "owner"),
        )


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("a2a_tasks", conn):
        op.drop_table("a2a_tasks")
