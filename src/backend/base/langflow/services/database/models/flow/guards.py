"""Application-level guards for locked flow mutations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from langflow.services.database.models.flow.model import Flow

LOCKED_FLOW_DETAIL = "Flow is locked. Unlock it before making changes."


class LockedFlowError(RuntimeError):
    """Raised when a mutation targets a locked flow."""


def ensure_flow_unlocked(flow: Flow) -> None:
    """Raise when *flow* is currently locked."""
    if getattr(flow, "locked", False) is True:
        raise LockedFlowError(LOCKED_FLOW_DETAIL)


def ensure_flow_update_allowed(flow: Flow, update_data: Mapping[str, Any]) -> None:
    """Allow updates to unlocked flows and unlock-only updates to locked flows.

    API clients commonly send the full current flow when toggling the lock. We
    therefore compare payload values with the persisted row and allow the
    request when ``locked=False`` is the only effective change.
    """
    if getattr(flow, "locked", False) is not True:
        return

    changed_fields = {
        field_name for field_name, new_value in update_data.items() if getattr(flow, field_name, None) != new_value
    }
    if changed_fields == {"locked"} and update_data.get("locked") is False:
        return

    raise LockedFlowError(LOCKED_FLOW_DETAIL)
