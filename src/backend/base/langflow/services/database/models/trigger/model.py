"""Tables for triggers, their event ledger, and the leases that serialize work.

Five tables ship in one migration so the later trigger tickets (TRG-3 listener
process, TRG-4 provider ingress, TRG-5/TRG-6 provider triggers) add behaviour
without another schema change:

``trigger``
    Authoritative for state, binding, pinning, and identity. The canvas node is
    authoritative only for schedule *fields*, which reconciliation copies into
    ``config`` on every flow save.
``trigger_event``
    The at-least-once ledger. ``uq_trigger_event_trigger_dedupe`` is the
    deduplication guarantee: it is enforced by the database, not by application
    code, so two replicas racing the same tick or the same provider redelivery
    can only produce one row.
``trigger_lease``
    Named singleton leases (the dispatcher loop, the schedule tick producer).
``trigger_listener_lease``
    One live listener per connection, for the TRG-3 listener process.
``trigger_subscription``
    Provider-side subscription/watch records for TRG-4 and TRG-6.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - SQLModel resolves annotations at runtime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import JSON, Column, DateTime, Field, SQLModel, func

from langflow.services.database.models.trigger.schemas import (
    TriggerBindingTarget,
    TriggerEventState,
    TriggerSessionPolicy,
    TriggerState,
    TriggerSubscriptionState,
)

# JSONB on Postgres (GIN-indexable), JSON elsewhere — the variant every other
# JSON column in this schema uses.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")


def _values(enum_cls: type) -> str:
    """Render an enum as a SQL ``IN`` list for a CheckConstraint."""
    return ", ".join(f"'{member.value}'" for member in enum_cls)


class Trigger(SQLModel, table=True):  # type: ignore[call-arg]
    """One armed trigger on one flow, owned by one user."""

    __tablename__ = "trigger"
    __table_args__ = (
        CheckConstraint(f"state IN ({_values(TriggerState)})", name="ck_trigger_state"),
        CheckConstraint(f"binding_target IN ({_values(TriggerBindingTarget)})", name="ck_trigger_binding_target"),
        CheckConstraint(f"session_policy IN ({_values(TriggerSessionPolicy)})", name="ck_trigger_session_policy"),
        CheckConstraint("concurrency_limit >= 1", name="ck_trigger_concurrency_limit_positive"),
        CheckConstraint("max_attempts >= 1", name="ck_trigger_max_attempts_positive"),
        # Reconciliation identity: one trigger row per canvas node. Partial so
        # API-created triggers (no node) are unconstrained.
        Index(
            "uq_trigger_flow_node",
            "flow_id",
            "node_id",
            unique=True,
            sqlite_where=sa.text("node_id IS NOT NULL"),
            postgresql_where=sa.text("node_id IS NOT NULL"),
        ),
        Index("ix_trigger_state_next_fire_at", "state", "next_fire_at"),
        Index("uq_trigger_public_id", "public_id", unique=True),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("flow.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    # The trigger owner. Runs execute as this identity; a deleted user takes the
    # trigger with them (a headless run with no owner has no principal to be).
    user_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    name: str = Field(sa_column=Column(sa.String(255), nullable=False))
    kind: str = Field(sa_column=Column(sa.String(64), nullable=False, index=True))
    provider: str | None = Field(default=None, sa_column=Column(sa.String(64), nullable=True))
    node_id: str | None = Field(default=None, sa_column=Column(sa.String(255), nullable=True))
    connection_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("connection.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JsonVariant, nullable=False))
    # Provider cursors / delta tokens (TRG-6). Kept off ``config`` so a canvas
    # save that rewrites config never clobbers a poll cursor.
    provider_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JsonVariant, nullable=False))
    state: str = Field(
        default=TriggerState.PENDING.value,
        sa_column=Column(sa.String(24), nullable=False, index=True, server_default=TriggerState.PENDING.value),
    )
    binding_target: str = Field(
        default=TriggerBindingTarget.FLOW.value,
        sa_column=Column(sa.String(16), nullable=False, server_default=TriggerBindingTarget.FLOW.value),
    )
    deployment_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("deployment.id", ondelete="SET NULL"), nullable=True),
    )
    # Pin. When set, dispatch builds from this version's data instead of the
    # saved flow, so canvas edits do not change what runs until the pin moves.
    flow_version_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("flow_version.id", ondelete="SET NULL"), nullable=True),
    )
    session_policy: str = Field(
        default=TriggerSessionPolicy.PER_EVENT.value,
        sa_column=Column(sa.String(16), nullable=False, server_default=TriggerSessionPolicy.PER_EVENT.value),
    )
    concurrency_limit: int = Field(sa_column=Column(sa.Integer(), nullable=False, server_default="1"))
    max_attempts: int = Field(sa_column=Column(sa.Integer(), nullable=False, server_default="5"))
    # TRG-4 ingress: opaque per-trigger public id and the HMAC secret for the
    # generic signed-webhook route. Both stay NULL until an ingress route mints
    # them, so no ingress migration is needed later.
    public_id: str | None = Field(default=None, sa_column=Column(sa.String(64), nullable=True))
    signing_secret_encrypted: str | None = Field(default=None, sa_column=Column(sa.Text(), nullable=True))
    next_fire_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_fired_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_error: str | None = Field(default=None, sa_column=Column(sa.Text(), nullable=True))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class TriggerEvent(SQLModel, table=True):  # type: ignore[call-arg]
    """One fired occurrence of a trigger; the unit the dispatcher leases."""

    __tablename__ = "trigger_event"
    __table_args__ = (
        # THE deduplication guarantee. Application code never checks first.
        UniqueConstraint("trigger_id", "dedupe_key", name="uq_trigger_event_trigger_dedupe"),
        CheckConstraint(f"state IN ({_values(TriggerEventState)})", name="ck_trigger_event_state"),
        CheckConstraint("attempt >= 0", name="ck_trigger_event_attempt_non_negative"),
        Index("ix_trigger_event_state_available_at", "state", "available_at"),
        Index("ix_trigger_event_trigger_created_at", "trigger_id", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    trigger_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("trigger.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    dedupe_key: str = Field(sa_column=Column(sa.String(255), nullable=False))
    state: str = Field(
        default=TriggerEventState.PENDING.value,
        sa_column=Column(sa.String(16), nullable=False, server_default=TriggerEventState.PENDING.value),
    )
    attempt: int = Field(sa_column=Column(sa.Integer(), nullable=False, server_default="0"))
    available_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    lease_owner: str | None = Field(default=None, sa_column=Column(sa.String(128), nullable=True))
    lease_expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JsonVariant, nullable=False))
    session_id: str | None = Field(default=None, sa_column=Column(sa.String(255), nullable=True))
    # No FK to ``job``: the job row is purgeable on its own retention schedule and
    # a purged job must not cascade-delete ledger history.
    job_id: UUID | None = Field(default=None, sa_column=Column(sa.Uuid(), nullable=True))
    replay_of_event_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("trigger_event.id", ondelete="SET NULL"), nullable=True),
    )
    error: str | None = Field(default=None, sa_column=Column(sa.Text(), nullable=True))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class TriggerLease(SQLModel, table=True):  # type: ignore[call-arg]
    """A named singleton lease (``dispatcher``, ``scheduler``, ``purge``).

    One row per loop name. The holder renews ``heartbeat_at``; any process may
    steal the lease once ``expires_at`` has passed, which is what makes the
    "exactly one tick across N replicas" guarantee survive a hard kill.
    """

    __tablename__ = "trigger_lease"

    name: str = Field(sa_column=Column(sa.String(64), primary_key=True, nullable=False))
    owner: str = Field(sa_column=Column(sa.String(128), nullable=False))
    acquired_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    heartbeat_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class TriggerListenerLease(SQLModel, table=True):  # type: ignore[call-arg]
    """One live listener per connection, for the TRG-3 listener process."""

    __tablename__ = "trigger_listener_lease"

    connection_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("connection.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
    )
    holder: str = Field(sa_column=Column(sa.String(128), nullable=False))
    acquired_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    heartbeat_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


class TriggerSubscription(SQLModel, table=True):  # type: ignore[call-arg]
    """A provider-side subscription/watch backing a push trigger (TRG-4, TRG-6)."""

    __tablename__ = "trigger_subscription"
    __table_args__ = (
        CheckConstraint(f"state IN ({_values(TriggerSubscriptionState)})", name="ck_trigger_subscription_state"),
        UniqueConstraint("provider", "provider_subscription_id", name="uq_trigger_subscription_provider_external_id"),
        Index("ix_trigger_subscription_renew_after", "state", "renew_after"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    trigger_id: UUID = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("trigger.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    connection_id: UUID | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("connection.id", ondelete="SET NULL"), nullable=True),
    )
    provider: str = Field(sa_column=Column(sa.String(64), nullable=False))
    provider_subscription_id: str = Field(sa_column=Column(sa.String(255), nullable=False))
    # Digest, never the token itself: the value is compared, never replayed.
    client_state_digest: str | None = Field(default=None, sa_column=Column(sa.String(64), nullable=True))
    provider_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JsonVariant, nullable=False))
    state: str = Field(
        default=TriggerSubscriptionState.PENDING.value,
        sa_column=Column(sa.String(16), nullable=False, server_default=TriggerSubscriptionState.PENDING.value),
    )
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    renew_after: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    lease_owner: str | None = Field(default=None, sa_column=Column(sa.String(128), nullable=True))
    lease_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
