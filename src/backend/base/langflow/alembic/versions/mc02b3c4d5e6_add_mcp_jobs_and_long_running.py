"""add_mcp_jobs_and_long_running

Adds:
  - flow.long_running (nullable Boolean, default False) — flips MCP tool calls
    to return a job handle instead of blocking on the synchronous run.
  - flow.default_timeout_s (nullable Integer, default 3600) — per-flow worker
    timeout for long_running jobs (validated 60-86400 at the API layer).
  - mcp_jobs table — persistent record of MCP tool invocations that run via
    the job queue: status, progress, result, error, callback URL, and the
    project / user / flow ownership needed for multi-tenancy filtering.

Phase: EXPAND

Revision ID: mc02b3c4d5e6
Revises: mb01b2c3d4e5
Create Date: 2026-05-12 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on Postgres, JSON elsewhere — matches the JsonVariant used on the
# MCPJob SQLModel. Declaring just sa.JSON() in the migration would cause
# alembic's autogenerate check to detect a phantom type diff on every run.
_JSON_VARIANT = sa.JSON().with_variant(JSONB(), "postgresql")

revision: str = "mc02b3c4d5e6"  # pragma: allowlist secret
down_revision: str | None = "mb01b2c3d4e5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    #  flow.long_running, flow.default_timeout_s                          #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if not migration.column_exists("flow", "long_running", conn):
            batch_op.add_column(
                sa.Column(
                    "long_running",
                    sa.Boolean(),
                    nullable=True,
                    server_default=sa.false(),
                )
            )
        if not migration.column_exists("flow", "default_timeout_s", conn):
            batch_op.add_column(
                sa.Column(
                    "default_timeout_s",
                    sa.Integer(),
                    nullable=True,
                    server_default=sa.text("3600"),
                )
            )

    # ------------------------------------------------------------------ #
    #  mcp_jobs                                                           #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("mcp_jobs", conn):
        op.create_table(
            "mcp_jobs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "project_id",
                sa.Uuid(),
                sa.ForeignKey("folder.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "flow_id",
                sa.Uuid(),
                sa.ForeignKey("flow.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tool_name", sa.String(length=255), nullable=False),
            sa.Column("inputs", _JSON_VARIANT, nullable=False),
            # status is Text() (not VARCHAR(n)) to match the SQLModel field —
            # the model stores enum values as TEXT so future states can be added
            # without an ALTER. Width-limiting would create a phantom-diff.
            sa.Column(
                "status",
                sa.Text(),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("result", _JSON_VARIANT, nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("callback_url", sa.String(length=2048), nullable=True),
            sa.Column(
                "created_by",
                sa.Uuid(),
                sa.ForeignKey("user.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        # Single-column indexes match the ``index=True`` flags on the SQLModel
        # fields. Composite indexes would phantom-diff against the model on
        # every autogenerate run.
        op.create_index("ix_mcp_jobs_project_id", "mcp_jobs", ["project_id"])
        op.create_index("ix_mcp_jobs_flow_id", "mcp_jobs", ["flow_id"])
        op.create_index("ix_mcp_jobs_status", "mcp_jobs", ["status"])


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("mcp_jobs", conn):
        op.drop_index("ix_mcp_jobs_status", table_name="mcp_jobs")
        op.drop_index("ix_mcp_jobs_flow_id", table_name="mcp_jobs")
        op.drop_index("ix_mcp_jobs_project_id", table_name="mcp_jobs")
        op.drop_table("mcp_jobs")

    with op.batch_alter_table("flow", schema=None) as batch_op:
        if migration.column_exists("flow", "default_timeout_s", conn):
            batch_op.drop_column("default_timeout_s")
        if migration.column_exists("flow", "long_running", conn):
            batch_op.drop_column("long_running")
