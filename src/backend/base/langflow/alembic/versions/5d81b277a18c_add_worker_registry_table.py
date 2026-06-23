"""add worker_registry table for the background worker fleet roster.

Revision ID: 5d81b277a18c
Revises: 8ce44e4858c6
Create Date: 2026-06-05 12:48:44.856568

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d81b277a18c"  # pragma: allowlist secret
down_revision: str | None = "8ce44e4858c6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if not migration.table_exists("worker_registry", conn):
        op.create_table(
            "worker_registry",
            sa.Column("owner", sa.String(), nullable=False),
            sa.Column("pid", sa.Integer(), nullable=False),
            sa.Column("host", sa.String(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "state",
                sa.Enum("idle", "busy", name="worker_state_enum"),
                nullable=False,
            ),
            sa.Column("current_job_id", sa.Uuid(), nullable=True),
            sa.PrimaryKeyConstraint("owner"),
        )
        with op.batch_alter_table("worker_registry", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_worker_registry_last_heartbeat"),
                ["last_heartbeat"],
                unique=False,
            )


def downgrade() -> None:
    from langflow.utils import migration

    conn = op.get_bind()
    if migration.table_exists("worker_registry", conn):
        with op.batch_alter_table("worker_registry", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_worker_registry_last_heartbeat"))
        op.drop_table("worker_registry")

    # Alembic does not drop named enums automatically; do it explicitly on Postgres.
    if conn.dialect.name == "postgresql":
        sa.Enum(name="worker_state_enum").drop(conn, checkfirst=True)
