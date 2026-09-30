"""add execution_signals table for cooperative job control.

Revision ID: 8ce44e4858c6
Revises: b026885b89c8
Create Date: 2026-06-03 10:10:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8ce44e4858c6"  # pragma: allowlist secret
down_revision: str | None = "b026885b89c8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("execution_signals", conn):
        op.create_table(
            "execution_signals",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("job_id", sa.Uuid(), nullable=False),
            sa.Column(
                "signal_type",
                sa.Enum("stop", name="execution_signal_type_enum"),
                nullable=False,
            ),
            sa.Column("data", _JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("execution_signals", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_execution_signals_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_execution_signals_job_id"), ["job_id"], unique=False)


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("execution_signals", conn):
        op.drop_table("execution_signals")
    # Drop the postgres enum type explicitly; sqlite has no standalone enum type.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="execution_signal_type_enum").drop(bind, checkfirst=True)
