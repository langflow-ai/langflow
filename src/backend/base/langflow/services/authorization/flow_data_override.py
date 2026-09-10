"""Whether a caller's run-time graph override may be honored.

``POST /api/v2/workflows`` and ``POST /api/v1/build/{id}/flow`` both accept
caller-supplied graph data so the canvas can run edits that are not saved yet.
Substituting a graph and running it under the owner's resources is an edit, so
it is gated on ``flow:write`` rather than on ownership: a caller who holds write
can already persist that graph and run it, so honoring the unsaved copy grants
nothing new, while an execute-only caller still cannot choose what runs.

The verdict is resolved once per request in an async authorization step and
read by the synchronous request gates, which run in all three execution modes.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

from fastapi import HTTPException

from langflow.api.utils.execution_errors import caller_owns_flow
from langflow.services.authorization.actions import FlowAction
from langflow.services.authorization.guards import ensure_flow_permission

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import FlowRead
    from langflow.services.database.models.user.model import UserRead

# Default False so an unresolved request falls back to owner-only overrides,
# which is the behavior every caller had before the verdict existed.
_flow_data_override_allowed: ContextVar[bool] = ContextVar(
    "langflow_flow_data_override_allowed",
    default=False,
)


async def resolve_flow_data_override(current_user: UserRead, flow: FlowRead) -> bool:
    """Resolve and remember whether this caller may override the stored graph."""
    allowed = caller_owns_flow(flow, current_user)
    if not allowed:
        try:
            await ensure_flow_permission(
                current_user,
                FlowAction.WRITE,
                flow_id=flow.id,
                flow_user_id=flow.user_id,
                workspace_id=getattr(flow, "workspace_id", None),
                folder_id=getattr(flow, "folder_id", None),
            )
        except HTTPException:
            allowed = False
        else:
            allowed = True
    _flow_data_override_allowed.set(allowed)
    return allowed


def flow_data_override_allowed() -> bool:
    """Return the verdict resolved for the current request."""
    return _flow_data_override_allowed.get()
