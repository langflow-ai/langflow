"""Durable storage for A2A protocol tasks."""

from typing import Any

from sqlalchemy import JSON, Column
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
