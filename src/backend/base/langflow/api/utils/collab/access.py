"""Authentication and authorization helpers for flow collaboration sockets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from lfx.services.deps import session_scope_readonly

from langflow.api.utils.collab.operations import FlowOperationApplyError
from langflow.api.v1.flows_helpers import _read_flow
from langflow.services.auth.utils import get_current_user_for_websocket
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import deny_to_404
from langflow.services.database.models.user.model import User, UserRead

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession
    from starlette.websockets import WebSocket

    from langflow.services.database.models.flow.model import Flow


@dataclass(frozen=True)
class FlowCollaborationAccess:
    current_user: UserRead
    starting_revision: int


class FlowCollaborationAccessError(Exception):
    """User-facing session error for collaboration access checks."""

    def __init__(self, *, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


async def validate_flow_collaboration_access(websocket: WebSocket, flow_id: UUID) -> FlowCollaborationAccess:
    """Authenticate the socket user and verify initial read access to the flow."""
    async with session_scope_readonly() as session:
        authenticated_user = await get_current_user_for_websocket(websocket, session)
        current_user = UserRead.model_validate(authenticated_user, from_attributes=True)

    async with session_scope_readonly() as session:
        flow = await _get_readable_flow(session, flow_id, current_user)
        starting_revision = flow.latest_operation_revision

    return FlowCollaborationAccess(
        current_user=current_user,
        starting_revision=starting_revision,
    )


async def validate_flow_access(
    session: AsyncSession,
    flow_id: UUID,
    current_user: User | UserRead,
) -> None:
    """Raise if the user can no longer read the flow."""
    await _get_readable_flow(session, flow_id, current_user)


async def _get_readable_flow(
    session: AsyncSession,
    flow_id: UUID,
    current_user: User | UserRead,
) -> Flow:
    flow = await _read_flow(session=session, flow_id=flow_id, user_id=current_user.id)
    if flow is None:
        raise FlowCollaborationAccessError(code="not_found", detail="Flow not found")

    try:
        await ensure_flow_permission(
            current_user,
            FlowAction.READ,
            flow_id=flow_id,
            flow_user_id=flow.user_id,
            workspace_id=flow.workspace_id,
            folder_id=flow.folder_id,
        )
    except HTTPException as exc:
        mapped = deny_to_404(exc, detail="Flow not found")
        raise FlowCollaborationAccessError(code="unauthorized", detail=str(mapped.detail)) from exc

    return flow


async def ensure_operation_write_permission(
    session: AsyncSession,
    flow_id: UUID,
    current_user: User | UserRead,
) -> None:
    """Raise a structured operation error when the actor cannot write to the flow."""
    flow = await _read_flow(session=session, flow_id=flow_id, user_id=current_user.id)
    if flow is None:
        raise FlowOperationApplyError(status_code=404, detail="Flow not found")

    try:
        await ensure_flow_permission(
            current_user,
            FlowAction.WRITE,
            flow_id=flow_id,
            flow_user_id=flow.user_id,
            workspace_id=flow.workspace_id,
            folder_id=flow.folder_id,
        )
    except HTTPException as exc:
        mapped = deny_to_404(exc, detail="Flow not found")
        raise FlowOperationApplyError(status_code=mapped.status_code, detail=str(mapped.detail)) from exc
