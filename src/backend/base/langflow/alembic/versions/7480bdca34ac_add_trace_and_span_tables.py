"""Add trace and span tables for native tracing

Revision ID: 7480bdca34ac
Revises: b1c2d3e4f5a6
Create Date: 2026-02-27 11:57:29.645080

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "7480bdca34ac"  # pragma: allowlist secret
down_revision: str | None = "b1c2d3e4f5a6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create trace table
    if not migration.table_exists("trace", conn):
        op.create_table(
            "trace",
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sa.Enum("unset", "ok", "error", name="spanstatus"), nullable=False),
            sa.Column("start_time", sa.DateTime(), nullable=False),
            sa.Column("end_time", sa.DateTime(), nullable=True),
            sa.Column("total_latency_ms", sa.Integer(), nullable=False),
            sa.Column("total_tokens", sa.Integer(), nullable=False),
            sa.Column("total_cost", sa.Float(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("trace", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_trace_flow_id"), ["flow_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_trace_session_id"), ["session_id"], unique=False)

    # Create span table
    if not migration.table_exists("span", conn):
        op.create_table(
            "span",
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "span_type",
                sa.Enum("chain", "llm", "tool", "retriever", "embedding", "parser", "agent", name="spantype"),
                nullable=False,
            ),
            sa.Column("status", sa.Enum("unset", "ok", "error", name="spanstatus"), nullable=False),
            sa.Column("start_time", sa.DateTime(), nullable=False),
            sa.Column("end_time", sa.DateTime(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=False),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "span_kind",
                sa.Enum("INTERNAL", "CLIENT", "SERVER", "PRODUCER", "CONSUMER", name="spankind"),
                nullable=False,
            ),
            sa.Column("attributes", sa.JSON(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("trace_id", sa.Uuid(), nullable=False),
            sa.Column("parent_span_id", sa.Uuid(), nullable=True),
            sa.ForeignKeyConstraint(["parent_span_id"], ["span.id"]),
            sa.ForeignKeyConstraint(["trace_id"], ["trace.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("span", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_span_parent_span_id"), ["parent_span_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_span_trace_id"), ["trace_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    # Drop span table first (depends on trace)
    if migration.table_exists("span", conn):
        with op.batch_alter_table("span", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_span_trace_id"))
            batch_op.drop_index(batch_op.f("ix_span_parent_span_id"))
        op.drop_table("span")

    # Drop trace table
    if migration.table_exists("trace", conn):
        with op.batch_alter_table("trace", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_trace_session_id"))
            batch_op.drop_index(batch_op.f("ix_trace_flow_id"))
        op.drop_table("trace")

    # Drop ENUMs (PostgreSQL only)
    if conn.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS spanstatus")
        op.execute("DROP TYPE IF EXISTS spantype")
        op.execute("DROP TYPE IF EXISTS spankind")
