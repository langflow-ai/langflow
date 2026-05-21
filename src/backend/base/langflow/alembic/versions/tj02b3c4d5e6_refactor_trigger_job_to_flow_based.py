"""refactor_trigger_job_to_flow_based

The trigger feature is moving from a standalone ``trigger`` table + REST
CRUD model to an in-flow component model. The schedule now lives as a
``CronTrigger`` node inside ``flow.data``; ``trigger_job`` becomes a
plain work queue keyed by ``(flow_id, component_id)``.

Migration steps:

  1. Purge any rows in ``trigger_job`` — they reference ``trigger.id``
     which is about to disappear, and the data model is changing
     anyway (we never shipped this to anyone).
  2. Rebuild ``trigger_job`` via ``batch_alter_table`` so SQLite can
     drop the ``trigger_id`` FK column and add ``flow_id`` and
     ``component_id`` in a single table recreation.
  3. Drop the ``trigger`` table.
  4. On Postgres only, drop the ``trigger_type_enum`` type that the
     prior migration created.

The downgrade restores the prior schema shape but does NOT restore the
purged rows — there is no migration path back to a ``trigger.id`` we
no longer have. This is intentional: the prior schema was never
deployed externally.

Revision ID: tj02b3c4d5e6
Revises: tg01a2b3c4d5
Create Date: 2026-05-21 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "tj02b3c4d5e6"  # pragma: allowlist secret
down_revision: str | None = "tg01a2b3c4d5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Purge — see file docstring for rationale.
    if migration.table_exists("trigger_job", conn):
        op.execute("DELETE FROM trigger_job")

        # 2. Rebuild via batch so SQLite can recreate the table with
        #    the new column set in one shot. The reuse of
        #    ``job_status_enum`` continues — the column type is unchanged.
        with op.batch_alter_table("trigger_job", schema=None) as batch_op:
            existing_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("trigger_job")}

            # Drop the trigger_id FK and indexes first.
            if "ix_trigger_job_trigger_id" in existing_indexes:
                batch_op.drop_index("ix_trigger_job_trigger_id")
            if "ix_trigger_job_status_scheduled_at" in existing_indexes:
                batch_op.drop_index("ix_trigger_job_status_scheduled_at")
            if migration.column_exists("trigger_job", "trigger_id", conn):
                batch_op.drop_column("trigger_id")

            # Add the new ownership columns.
            if not migration.column_exists("trigger_job", "flow_id", conn):
                batch_op.add_column(
                    sa.Column(
                        "flow_id",
                        sa.Uuid(),
                        sa.ForeignKey("flow.id", ondelete="CASCADE"),
                        nullable=False,
                    ),
                )
            if not migration.column_exists("trigger_job", "component_id", conn):
                batch_op.add_column(
                    sa.Column("component_id", sa.String(), nullable=False),
                )

        # Recreate indexes after the rebuild.
        op.create_index("ix_trigger_job_flow_id", "trigger_job", ["flow_id"])
        op.create_index("ix_trigger_job_component_id", "trigger_job", ["component_id"])
        # Composite index on the hot claim filter survives across the
        # rebuild — recreate it explicitly so SQLite reflects the new
        # column set.
        op.create_index(
            "ix_trigger_job_status_scheduled_at",
            "trigger_job",
            ["status", "scheduled_at"],
        )

    # 3. The ``trigger`` table is no longer the source of truth.
    if migration.table_exists("trigger", conn):
        op.drop_index("ix_trigger_trigger_type", table_name="trigger")
        op.drop_index("ix_trigger_is_active", table_name="trigger")
        op.drop_index("ix_trigger_user_id", table_name="trigger")
        op.drop_index("ix_trigger_flow_id", table_name="trigger")
        op.drop_table("trigger")

    # 4. The trigger_type_enum was created exclusively for the prior
    #    ``trigger`` table. Drop it on Postgres so future migrations
    #    (or a downgrade through this one) don't trip over an orphan
    #    type. SQLite has no separate enum type — column degrades to a
    #    checked string.
    if conn.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS trigger_type_enum")


def downgrade() -> None:
    conn = op.get_bind()

    # Recreate the ``trigger`` table (and its enum on Postgres).
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
                sa.Enum("cron", name="trigger_type_enum"),
                nullable=False,
            ),
            sa.Column("cron_expression", sa.String(), nullable=True),
            sa.Column("timezone", sa.String(), nullable=False, server_default=sa.text("'UTC'")),
            sa.Column("payload", sa.JSON(), nullable=True),
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

    # Rebuild trigger_job back to the prior shape: trigger_id NOT NULL,
    # no flow_id / component_id. We purge again on the way down — there
    # are no synthesised trigger.id values we could backfill with.
    if migration.table_exists("trigger_job", conn):
        op.execute("DELETE FROM trigger_job")
        with op.batch_alter_table("trigger_job", schema=None) as batch_op:
            existing_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("trigger_job")}
            for ix in (
                "ix_trigger_job_flow_id",
                "ix_trigger_job_component_id",
                "ix_trigger_job_status_scheduled_at",
            ):
                if ix in existing_indexes:
                    batch_op.drop_index(ix)
            if migration.column_exists("trigger_job", "component_id", conn):
                batch_op.drop_column("component_id")
            if migration.column_exists("trigger_job", "flow_id", conn):
                batch_op.drop_column("flow_id")
            if not migration.column_exists("trigger_job", "trigger_id", conn):
                batch_op.add_column(
                    sa.Column(
                        "trigger_id",
                        sa.Uuid(),
                        sa.ForeignKey("trigger.id", ondelete="CASCADE"),
                        nullable=False,
                    ),
                )
        op.create_index("ix_trigger_job_trigger_id", "trigger_job", ["trigger_id"])
        op.create_index(
            "ix_trigger_job_status_scheduled_at",
            "trigger_job",
            ["status", "scheduled_at"],
        )
