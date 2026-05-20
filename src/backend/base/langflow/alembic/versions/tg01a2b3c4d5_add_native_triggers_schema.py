"""add_native_triggers_schema

Adds the two tables backing the native triggers feature:

* ``trigger`` — one row per cron schedule.
* ``trigger_job`` — the work queue drained by the in-process worker.

``trigger_type_enum`` is created in this migration. The job status enum
is reused: ``trigger_job.status`` shares the existing
``job_status_enum`` (created by the original ``job`` migration), so the
column type is declared with ``create_type=False`` to keep Alembic
from issuing a duplicate ``CREATE TYPE`` on Postgres. SQLite stores
the column as a checked string and the flag is a no-op.

Revision ID: tg01a2b3c4d5
Revises: mb01b2c3d4e5
Create Date: 2026-05-20 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "tg01a2b3c4d5"  # pragma: allowlist secret
down_revision: str | None = "mb01b2c3d4e5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ``trigger_type`` is new and owned by this migration. The job status
# enum is owned by the ``job`` table's migration; we reuse it.
_TRIGGER_TYPE_VALUES = ("cron",)
_JOB_STATUS_VALUES = (
    "queued",
    "in_progress",
    "completed",
    "failed",
    "cancelled",
    "timed_out",
)

# JSONB on Postgres, plain JSON elsewhere — same variant the rest of
# the schema uses for free-form JSON columns.
_JsonVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    #  trigger                                                            #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("trigger", conn):
        op.create_table(
            "trigger",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "flow_id",
                sa.Uuid(),
                sa.ForeignKey("flow.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column(
                "trigger_type",
                sa.Enum(*_TRIGGER_TYPE_VALUES, name="trigger_type_enum"),
                nullable=False,
            ),
            sa.Column("cron_expression", sa.String(), nullable=True),
            sa.Column("timezone", sa.String(), nullable=False, server_default=sa.text("'UTC'")),
            sa.Column("payload", _JsonVariant, nullable=True),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "name", name="uq_trigger_user_name"),
        )
        op.create_index("ix_trigger_flow_id", "trigger", ["flow_id"])
        op.create_index("ix_trigger_user_id", "trigger", ["user_id"])
        op.create_index("ix_trigger_is_active", "trigger", ["is_active"])
        op.create_index("ix_trigger_trigger_type", "trigger", ["trigger_type"])

    # ------------------------------------------------------------------ #
    #  trigger_job                                                        #
    # ------------------------------------------------------------------ #
    if not migration.table_exists("trigger_job", conn):
        # ``create_type=False``: the type is owned by the ``job`` migration.
        job_status_enum = sa.Enum(
            *_JOB_STATUS_VALUES,
            name="job_status_enum",
            create_type=False,
        )
        op.create_table(
            "trigger_job",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "trigger_id",
                sa.Uuid(),
                sa.ForeignKey("trigger.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", job_status_enum, nullable=False),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "run_job_id",
                sa.Uuid(),
                sa.ForeignKey("job.job_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_trigger_job_trigger_id", "trigger_job", ["trigger_id"])
        op.create_index("ix_trigger_job_run_job_id", "trigger_job", ["run_job_id"])
        # Composite index for the worker's hot path:
        #   WHERE status = 'queued' AND scheduled_at <= now()
        op.create_index(
            "ix_trigger_job_status_scheduled_at",
            "trigger_job",
            ["status", "scheduled_at"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Children before parents — trigger_job FKs reference trigger.
    if migration.table_exists("trigger_job", conn):
        op.drop_index("ix_trigger_job_status_scheduled_at", table_name="trigger_job")
        op.drop_index("ix_trigger_job_run_job_id", table_name="trigger_job")
        op.drop_index("ix_trigger_job_trigger_id", table_name="trigger_job")
        op.drop_table("trigger_job")

    if migration.table_exists("trigger", conn):
        op.drop_index("ix_trigger_trigger_type", table_name="trigger")
        op.drop_index("ix_trigger_is_active", table_name="trigger")
        op.drop_index("ix_trigger_user_id", table_name="trigger")
        op.drop_index("ix_trigger_flow_id", table_name="trigger")
        op.drop_table("trigger")

    # The job_status_enum belongs to the job migration — leave it alone.
    if conn.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS trigger_type_enum")
