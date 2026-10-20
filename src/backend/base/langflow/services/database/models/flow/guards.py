"""Application-level guards for locked flow mutations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow

LOCKED_FLOW_DETAIL = "Flow is locked. Unlock it before making changes."


class LockedFlowError(RuntimeError):
    """Raised when a mutation targets a locked flow."""


async def lock_flow_for_update(session: AsyncSession, flow: Flow) -> None:
    """Refresh *flow* while holding its database row lock until transaction end.

    Every writer of a flow's graph takes this lock before reading the flow and
    holds it through commit, conditional or not: the history's revision head is
    extended under it, and two writers extending it from the same head would
    record two transitions from one state.

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
    await session.refresh(flow, with_for_update=True)


async def lock_flow_for_read(session: AsyncSession, flow: Flow) -> None:
    """Hold *flow*'s row in shared mode until transaction end, for a consistent read of its history.

    On PostgreSQL, ``FOR SHARE`` lets readers proceed together while history
    maintenance, which deletes old rows under the exclusive lock, waits for
    them. Take it before any other read of the history: at READ COMMITTED
    every later statement then sees the state the lock was granted on, and
    nothing can delete rows under the read.

    SQLite has no row locks and is left alone.
    """
    if session.get_bind().dialect.name == "sqlite":
        return
    from sqlmodel import select

    from langflow.services.database.models.flow.model import Flow

    await session.exec(select(Flow.id).where(Flow.id == flow.id).with_for_update(read=True))


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
