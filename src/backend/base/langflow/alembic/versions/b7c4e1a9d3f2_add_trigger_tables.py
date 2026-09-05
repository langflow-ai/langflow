"""Add the trigger entity, event ledger, and trigger leases.

One migration creates every trigger table so the follow-on trigger tickets
(TRG-3 listener process, TRG-4 provider ingress, TRG-5/TRG-6 provider triggers)
ship without another schema change.

The unique constraint ``uq_trigger_event_trigger_dedupe`` is the deduplication
guarantee for the ledger: two dispatcher replicas racing the same tick, or a
provider redelivering the same event, are rejected by the database rather than
by application code.

Revision ID: b7c4e1a9d3f2
Revises: a7d8e9f0b1c2
Create Date: 2026-09-05

Phase: EXPAND
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on Postgres (GIN-indexable), JSON elsewhere — the variant the models use.
JsonVariant = sa.JSON().with_variant(JSONB(), "postgresql")

revision = "b7c4e1a9d3f2"  # pragma: allowlist secret
down_revision = "a7d8e9f0b1c2"  # pragma: allowlist secret
branch_labels = None
depends_on = None

_TRIGGER_STATES = "'pending', 'active', 'paused', 'expired', 'needs_reconnect', 'error', 'dead'"
_EVENT_STATES = "'pending', 'claimed', 'dispatched', 'completed', 'failed', 'dead'"
_SUBSCRIPTION_STATES = "'pending', 'active', 'expired', 'error'"

# Dropped in reverse dependency order so foreign keys never block a downgrade.
_TABLES_IN_DROP_ORDER = (
    "trigger_subscription",
    "trigger_listener_lease",
    "trigger_lease",
    "trigger_event",
    "trigger",
)


def _create_trigger() -> None:
    op.create_table(
        "trigger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flow_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("node_id", sa.String(255), nullable=True),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("config", JsonVariant, nullable=False),
        sa.Column("provider_state", JsonVariant, nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("binding_target", sa.String(16), nullable=False, server_default="flow"),
        sa.Column("deployment_id", sa.Uuid(), nullable=True),
        sa.Column("flow_version_id", sa.Uuid(), nullable=True),
        sa.Column("session_policy", sa.String(16), nullable=False, server_default="per_event"),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("public_id", sa.String(64), nullable=True),
        sa.Column("signing_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("next_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["connection.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployment.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_version.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(f"state IN ({_TRIGGER_STATES})", name="ck_trigger_state"),
        sa.CheckConstraint("binding_target IN ('flow', 'deployment')", name="ck_trigger_binding_target"),
        sa.CheckConstraint("session_policy IN ('per_event', 'shared')", name="ck_trigger_session_policy"),
        sa.CheckConstraint("concurrency_limit >= 1", name="ck_trigger_concurrency_limit_positive"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_trigger_max_attempts_positive"),
    )
    op.create_index("ix_trigger_flow_id", "trigger", ["flow_id"])
    op.create_index("ix_trigger_user_id", "trigger", ["user_id"])
    op.create_index("ix_trigger_connection_id", "trigger", ["connection_id"])
    op.create_index("ix_trigger_kind", "trigger", ["kind"])
    op.create_index("ix_trigger_state", "trigger", ["state"])
    op.create_index("ix_trigger_state_next_fire_at", "trigger", ["state", "next_fire_at"])
    op.create_index("uq_trigger_public_id", "trigger", ["public_id"], unique=True)
    # Partial: reconciliation keys one row per canvas node, while API-created
    # triggers (node_id NULL) stay unconstrained.
    op.create_index(
        "uq_trigger_flow_node",
        "trigger",
        ["flow_id", "node_id"],
        unique=True,
        sqlite_where=sa.text("node_id IS NOT NULL"),
        postgresql_where=sa.text("node_id IS NOT NULL"),
    )


def _create_trigger_event() -> None:
    op.create_table(
        "trigger_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trigger_id", sa.Uuid(), nullable=False),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", JsonVariant, nullable=False),
        sa.Column("session_id", sa.String(255), nullable=True),
        # Deliberately no FK: a purged job row must not cascade away ledger history.
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("replay_of_event_id", sa.Uuid(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["trigger_id"], ["trigger.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replay_of_event_id"], ["trigger_event.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trigger_id", "dedupe_key", name="uq_trigger_event_trigger_dedupe"),
        sa.CheckConstraint(f"state IN ({_EVENT_STATES})", name="ck_trigger_event_state"),
        sa.CheckConstraint("attempt >= 0", name="ck_trigger_event_attempt_non_negative"),
    )
    op.create_index("ix_trigger_event_trigger_id", "trigger_event", ["trigger_id"])
    op.create_index("ix_trigger_event_created_at", "trigger_event", ["created_at"])
    op.create_index("ix_trigger_event_state_available_at", "trigger_event", ["state", "available_at"])
    op.create_index("ix_trigger_event_trigger_created_at", "trigger_event", ["trigger_id", "created_at"])


def _create_trigger_lease() -> None:
    op.create_table(
        "trigger_lease",
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )


def _create_trigger_listener_lease() -> None:
    op.create_table(
        "trigger_listener_lease",
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("holder", sa.String(128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["connection.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("connection_id"),
    )


def _create_trigger_subscription() -> None:
    op.create_table(
        "trigger_subscription",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trigger_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_subscription_id", sa.String(255), nullable=False),
        sa.Column("client_state_digest", sa.String(64), nullable=True),
        sa.Column("provider_state", JsonVariant, nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renew_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["trigger_id"], ["trigger.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["connection.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_subscription_id", name="uq_trigger_subscription_provider_external_id"
        ),
        sa.CheckConstraint(f"state IN ({_SUBSCRIPTION_STATES})", name="ck_trigger_subscription_state"),
    )
    op.create_index("ix_trigger_subscription_trigger_id", "trigger_subscription", ["trigger_id"])
    op.create_index("ix_trigger_subscription_renew_after", "trigger_subscription", ["state", "renew_after"])


def upgrade() -> None:
    bind = op.get_bind()
    if not migration.table_exists("trigger", bind):
        _create_trigger()
    if not migration.table_exists("trigger_event", bind):
        _create_trigger_event()
    if not migration.table_exists("trigger_lease", bind):
        _create_trigger_lease()
    if not migration.table_exists("trigger_listener_lease", bind):
        _create_trigger_listener_lease()
    if not migration.table_exists("trigger_subscription", bind):
        _create_trigger_subscription()


def downgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES_IN_DROP_ORDER:
        if migration.table_exists(table, bind):
            op.drop_table(table)
