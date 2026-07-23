"""add a2a_checkpoints table for durable HITL resume of A2A tasks.

Revision ID: a2c8f1e3b4d6
Revises: 142ba6cd9317
Create Date: 2026-06-26 10:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a2c8f1e3b4d6"  # pragma: allowlist secret
down_revision: str | None = "142ba6cd9317"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("a2a_checkpoints", conn):
        op.create_table(
            "a2a_checkpoints",
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("checkpoint", _JSON, nullable=False),
            sa.PrimaryKeyConstraint("run_id"),
        )


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("a2a_checkpoints", conn):
        op.drop_table("a2a_checkpoints")
