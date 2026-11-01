"""Application-level guards for locked flow mutations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow

LOCKED_FLOW_DETAIL = "Flow is locked. Unlock it before making changes."


class LockedFlowError(RuntimeError):
    """Raised when a mutation targets a locked flow."""


async def lock_flow_for_update(session: AsyncSession, flow: Flow) -> None:
    """Refresh *flow* while holding the flow's write lock until transaction end.

    Every writer of a flow's graph takes this lock before reading the flow and
    holds it through commit, conditional or not: the history's revision head is
    extended under it, and two writers extending it from the same head would
    record two transitions from one state.

    On PostgreSQL the lock is the flow's operation-log advisory lock
    (``pg_advisory_xact_lock``), the same lock the multiplayer writers take,
    and not the flow's row lock: a multiplayer writer in WAL mode never touches
    the flow row. The refresh that follows the lock reads the flow as committed.

    SQLite ignores ``FOR UPDATE``. A no-op write takes its database-wide write
    lock instead, which is held until the transaction ends, and the refresh
    that follows reads the flow as committed.
    """
    if session.get_bind().dialect.name == "sqlite":
        from sqlmodel import update

        from langflow.services.database.models.flow.model import Flow

        await session.exec(
            update(Flow).where(Flow.id == flow.id).values(id=Flow.id).execution_options(synchronize_session=False)
        )
        await session.refresh(flow)
        return
    await lock_flow_oplog(session, flow.id)
    await session.refresh(flow)


async def lock_flow_oplog(session: AsyncSession, flow_id: UUID) -> None:
    """Take the flow's operation-log advisory lock until transaction end (PostgreSQL; no-op elsewhere).

    Take it before any row lock on the flow: multiplayer writers take this lock
    first and then write the flow row, so the reverse order could deadlock.
    """
    if session.get_bind().dialect.name != "postgresql":
        return
    from langflow.services.flow_multiplayer.oplog import lock_flow

    await lock_flow(session, flow_id)


async def lock_flows_oplog(session: AsyncSession, flow_ids: Iterable[UUID]) -> None:
    """Take several flows' operation-log locks, in one order (sorted ids), so two callers never deadlock."""
    for flow_id in sorted(set(flow_ids), key=str):
        await lock_flow_oplog(session, flow_id)


def ensure_flow_unlocked(flow: Flow) -> None:
    """Raise when *flow* is currently locked."""
    if getattr(flow, "locked", False) is True:
        raise LockedFlowError(LOCKED_FLOW_DETAIL)


def ensure_flow_update_allowed(
    flow: Flow,
    update_data: Mapping[str, Any],
    *,
    persisted_values: Mapping[str, Any] | None = None,
) -> None:
    """Allow updates to unlocked flows and safe updates to locked flows.

    API clients commonly send the full current flow when toggling the lock. We
    therefore compare payload values with the persisted row and allow no-op
    requests or requests where ``locked=False`` is the only effective change.

    ``persisted_values`` overrides ``flow``'s in-memory attribute for the
    fields it names when computing the diff. Atomic project replacement
    temporarily renames a flow (to free its name/endpoint_name for the
    requested set) before this guard runs; without the override, that
    in-memory rename would make ``name``/``endpoint_name`` look changed on
    every request to a locked flow, even one that changes nothing.
    """
    if getattr(flow, "locked", False) is not True:
        return

    persisted_values = persisted_values or {}
    changed_fields = {
        field_name
        for field_name, new_value in update_data.items()
        if persisted_values.get(field_name, getattr(flow, field_name, None)) != new_value
    }
    if not changed_fields or (changed_fields == {"locked"} and update_data.get("locked") is False):
        return

    raise LockedFlowError(LOCKED_FLOW_DETAIL)
