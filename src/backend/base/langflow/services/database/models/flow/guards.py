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
    """Refresh *flow* while holding its database row lock until transaction end."""
    await session.refresh(flow, with_for_update=True)


def ensure_flow_unlocked(flow: Flow) -> None:
    """Raise when *flow* is currently locked."""
    if getattr(flow, "locked", False) is True:
        raise LockedFlowError(LOCKED_FLOW_DETAIL)


def ensure_flow_update_allowed(flow: Flow, update_data: Mapping[str, Any]) -> None:
    """Allow updates to unlocked flows and safe updates to locked flows.

    API clients commonly send the full current flow when toggling the lock. We
    therefore compare payload values with the persisted row and allow no-op
    requests or requests where ``locked=False`` is the only effective change.
    """
    if getattr(flow, "locked", False) is not True:
        return

    changed_fields = {
        field_name for field_name, new_value in update_data.items() if getattr(flow, field_name, None) != new_value
    }
    if not changed_fields or (changed_fields == {"locked"} and update_data.get("locked") is False):
        return

    raise LockedFlowError(LOCKED_FLOW_DETAIL)
