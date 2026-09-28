"""Rows of a flow's operation history.

Each row stores a contiguous, inclusive range of revisions: one revision per
accepted operation, numbered by the server in commit order. Revision ``N`` is
the flow's graph right after operation ``N``. The ordered operations live in
``ops``, a versioned envelope that carries each operation's revision, actor and
request; ``actor_user_ids`` and ``request_ids`` are lookup lists derived from it.

Rows are append-only (see ``append_only``). A flow's rows never overlap and
leave no gaps; the service enforces that, since portable SQL constraints cannot.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 -- SQLModel resolves field types at runtime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.naming import conv
from sqlmodel import Field, SQLModel

from langflow.services.database.models.flow_operation import append_only

REVISION_RANGE_CHECK_NAME = "ck_flow_operation_revision_range"

# jsonb on PostgreSQL: the plain json type has no GIN operator class, and both
# lists are searched with containment (``@>``).
LookupList = JSON().with_variant(JSONB(), "postgresql")


class FlowOperation(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_operation"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), nullable=False))
    start_revision: int = Field(sa_column=Column(BigInteger, nullable=False))
    end_revision: int = Field(sa_column=Column(BigInteger, nullable=False))
    ops: dict = Field(sa_column=Column(JSON, nullable=False))
    actor_user_ids: list[str] = Field(sa_column=Column(LookupList, nullable=False))
    request_ids: list[str] = Field(sa_column=Column(LookupList, nullable=False))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    __table_args__ = (
        CheckConstraint("start_revision <= end_revision", name=conv(REVISION_RANGE_CHECK_NAME)),
        # Also serves range lookups: "the rows ending after revision R" is a
        # prefix scan of (flow_id, end_revision).
        UniqueConstraint("flow_id", "start_revision", name="uq_flow_operation_flow_id_start_revision"),
        UniqueConstraint("flow_id", "end_revision", name="uq_flow_operation_flow_id_end_revision"),
        Index(
            "ix_flow_operation_actor_user_ids",
            "actor_user_ids",
            postgresql_using="gin",
            postgresql_ops={"actor_user_ids": "jsonb_path_ops"},
            info={"dialects": ("postgresql",)},
        ).ddl_if(dialect="postgresql"),
        Index(
            "ix_flow_operation_request_ids",
            "request_ids",
            postgresql_using="gin",
            postgresql_ops={"request_ids": "jsonb_path_ops"},
            info={"dialects": ("postgresql",)},
        ).ddl_if(dialect="postgresql"),
    )


@event.listens_for(FlowOperation.__table__, "after_create")
def _install_append_only_triggers(target, connection, **_kwargs) -> None:  # noqa: ARG001
    for statement in append_only.create_statements(connection.dialect.name):
        connection.execute(text(statement))


@event.listens_for(FlowOperation.__table__, "after_drop")
def _remove_append_only_functions(target, connection, **_kwargs) -> None:  # noqa: ARG001
    for statement in append_only.drop_function_statements(connection.dialect.name):
        connection.execute(text(statement))
