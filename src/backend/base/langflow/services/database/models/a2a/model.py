"""Durable storage for A2A protocol tasks."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSONB on Postgres (GIN-indexable), JSON elsewhere — same variant as the other JSON columns.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")


class A2ATask(SQLModel, table=True):  # type: ignore[call-arg]
    """One A2A protocol Task, persisted so it survives restart and is visible across workers.

    ``task`` holds the whole protobuf ``Task`` as ``MessageToDict`` JSON; the A2A surface
    only does point lookups by id this slice, so a single blob is enough (a tasks/list or
    contextId filter would add decomposed columns later). The composite PK ``(id, owner)``
    mirrors the SDK TaskStore's owner-scoped keying — ``owner`` is '' on the anonymous public
    endpoint. ``id`` is declared first so ``session.get(A2ATask, (id, owner))`` passes the
    tuple in primary-key order.
    """

    __tablename__ = "a2a_tasks"

    id: str = Field(primary_key=True)
    owner: str = Field(default="", primary_key=True)
    task: dict[str, Any] = Field(sa_column=Column(JsonVariant, nullable=False))
    # Nothing prunes a2a_tasks yet, so the table grows unbounded. These let a retention reaper (or
    # an operator) prune by age; the DB maintains both, so the store needs no timestamp code.
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True),
    )


class A2ACheckpoint(SQLModel, table=True):  # type: ignore[call-arg]
    """A paused HITL run's graph checkpoint, so an A2A ``input-required`` task can be resumed.

    Keyed by ``run_id`` (the A2A task id, a UUID4); ``checkpoint`` is the lfx ``GraphCheckpoint``
    as ``model_dump`` JSON. Resume access is gated by the route's apikey auth, the unguessable
    task id, and a ``checkpoint.flow_id == flow_id`` check in ``_resume_flow`` (so a task parked
    under one flow can't be resumed via another's endpoint). Kept separate from ``a2a_tasks`` so
    the public Task blob never carries internal resume state. lfx-portable: only ``session_scope``
    + this table, no langflow job machinery.
    """

    __tablename__ = "a2a_checkpoints"

    run_id: str = Field(primary_key=True)
    checkpoint: dict[str, Any] = Field(sa_column=Column(JsonVariant, nullable=False))
