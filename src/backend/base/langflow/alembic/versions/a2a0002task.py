"""Add a2a_task table for DB-backed A2A task store

Revision ID: a2a0002task
Revises: a2a0001fields
Create Date: 2026-05-24 16:00:00.000000

Persists A2A task lifecycle state (previously in-memory) so tasks survive
restarts and are shared across workers.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "a2a0002task"
down_revision: str | None = "a2a0001fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore[union-attr]
    if "a2a_task" in inspector.get_table_names():
        return

    op.create_table(
        "a2a_task",
        sa.Column("task_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("context_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("flow_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("artifacts", JsonVariant, nullable=False),
        sa.Column("task_metadata", JsonVariant, nullable=False),
        sa.Column("status_message", JsonVariant, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("task_id"),
    )
    with op.batch_alter_table("a2a_task", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_a2a_task_task_id"), ["task_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_a2a_task_context_id"), ["context_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_a2a_task_flow_id"), ["flow_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_a2a_task_state"), ["state"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore[union-attr]
    if "a2a_task" not in inspector.get_table_names():
        return
    with op.batch_alter_table("a2a_task", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_a2a_task_state"))
        batch_op.drop_index(batch_op.f("ix_a2a_task_flow_id"))
        batch_op.drop_index(batch_op.f("ix_a2a_task_context_id"))
        batch_op.drop_index(batch_op.f("ix_a2a_task_task_id"))
    op.drop_table("a2a_task")
