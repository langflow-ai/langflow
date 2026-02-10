"""Add trace and span tables for native tracing

Revision ID: 3671f35245e5
Revises: fd531f8868b1
Create Date: 2026-01-28 04:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "3671f35245e5"
down_revision: str | None = "182e5471b900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create trace table
    if not migration.table_exists("trace", conn):
        op.create_table(
            "trace",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "status",
                sa.Enum("SUCCESS", "ERROR", "RUNNING", name="spanstatus"),
                nullable=False,
                server_default="RUNNING",
            ),
            sa.Column("start_time", sa.DateTime(), nullable=False),
            sa.Column("end_time", sa.DateTime(), nullable=True),
            sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_cost", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_trace_flow_id", "trace", ["flow_id"])
        op.create_index("ix_trace_session_id", "trace", ["session_id"])

    # Create span table
    if not migration.table_exists("span", conn):
        op.create_table(
            "span",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("trace_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("parent_span_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=True),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "span_type",
                sa.Enum("CHAIN", "LLM", "TOOL", "RETRIEVER", "EMBEDDING", "PARSER", "AGENT", name="spantype"),
                nullable=False,
                server_default="CHAIN",
            ),
            sa.Column(
                "status",
                sa.Enum("SUCCESS", "ERROR", "RUNNING", name="spanstatus"),
                nullable=False,
                server_default="RUNNING",
            ),
            sa.Column("start_time", sa.DateTime(), nullable=False),
            sa.Column("end_time", sa.DateTime(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("model_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("cost", sa.Float(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["trace_id"], ["trace.id"], name="fk_span_trace_id_trace"),
            sa.ForeignKeyConstraint(["parent_span_id"], ["span.id"], name="fk_span_parent_span_id_span"),
        )
        op.create_index("ix_span_trace_id", "span", ["trace_id"])
        op.create_index("ix_span_parent_span_id", "span", ["parent_span_id"])


def downgrade() -> None:
    conn = op.get_bind()

    # Drop span table first (depends on trace)
    if migration.table_exists("span", conn):
        op.drop_index("ix_span_parent_span_id", table_name="span")
        op.drop_index("ix_span_trace_id", table_name="span")
        op.drop_table("span")

    # Drop trace table
    if migration.table_exists("trace", conn):
        op.drop_index("ix_trace_session_id", table_name="trace")
        op.drop_index("ix_trace_flow_id", table_name="trace")
        op.drop_table("trace")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS spantype")
    op.execute("DROP TYPE IF EXISTS spanstatus")
