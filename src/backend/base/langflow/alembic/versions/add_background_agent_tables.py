"""Add background agent tables

Revision ID: kcl7kwcp1upb
Revises: 1b8b740a6fa3
Create Date: 2025-01-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Enum as SQLEnum

# revision identifiers, used by Alembic.
revision: str = "kcl7kwcp1upb"
down_revision: str | None = "1b8b740a6fa3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create background agent tables."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    tables = inspector.get_table_names()

    # Create trigger_type_enum
    trigger_type_enum = SQLEnum(
        "CRON", "INTERVAL", "DATE", "WEBHOOK", "EVENT",
        name="trigger_type_enum",
    )

    # Create agent_status_enum
    agent_status_enum = SQLEnum(
        "ACTIVE", "PAUSED", "STOPPED", "ERROR",
        name="agent_status_enum",
    )

    # Create backgroundagent table if it doesn't exist
    if "backgroundagent" not in tables:
        op.create_table(
            "backgroundagent",
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("flow_id", sa.UUID(), nullable=False),
            sa.Column("trigger_type", trigger_type_enum, nullable=False),
            sa.Column("trigger_config", sa.JSON(), nullable=True),
            sa.Column("input_config", sa.JSON(), nullable=True),
            sa.Column("status", agent_status_enum, nullable=False, server_default="STOPPED"),
            sa.Column("enabled", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_backgroundagent_flow_id"), "backgroundagent", ["flow_id"], unique=False)
        op.create_index(op.f("ix_backgroundagent_name"), "backgroundagent", ["name"], unique=False)
        op.create_index(op.f("ix_backgroundagent_user_id"), "backgroundagent", ["user_id"], unique=False)

    # Create backgroundagentexecution table if it doesn't exist
    if "backgroundagentexecution" not in tables:
        op.create_table(
            "backgroundagentexecution",
            sa.Column("agent_id", sa.UUID(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("trigger_source", sa.String(), nullable=True),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["backgroundagent.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_backgroundagentexecution_agent_id"),
            "backgroundagentexecution",
            ["agent_id"],
            unique=False,
        )


def downgrade() -> None:
    """Drop background agent tables."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    tables = inspector.get_table_names()

    # Drop backgroundagentexecution table if it exists
    if "backgroundagentexecution" in tables:
        op.drop_index(op.f("ix_backgroundagentexecution_agent_id"), table_name="backgroundagentexecution")
        op.drop_table("backgroundagentexecution")

    # Drop backgroundagent table if it exists
    if "backgroundagent" in tables:
        op.drop_index(op.f("ix_backgroundagent_user_id"), table_name="backgroundagent")
        op.drop_index(op.f("ix_backgroundagent_name"), table_name="backgroundagent")
        op.drop_index(op.f("ix_backgroundagent_flow_id"), table_name="backgroundagent")
        op.drop_table("backgroundagent")

    # Drop enums (PostgreSQL only)
    try:
        op.execute("DROP TYPE IF EXISTS agent_status_enum")
        op.execute("DROP TYPE IF EXISTS trigger_type_enum")
    except Exception:  # noqa: S110, BLE001
        # Silently ignore for non-PostgreSQL databases
        pass
