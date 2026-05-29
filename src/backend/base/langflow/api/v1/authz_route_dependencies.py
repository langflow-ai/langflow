"""FastAPI dependencies that fetch a resource and enforce authorization in one step."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.flows_helpers import _read_flow
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import deny_to_404
from langflow.services.database.models.flow.model import Flow, FlowCreate


async def _get_authorized_flow(
    act: FlowAction,
    *,
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> Flow:
    """Load a flow (share-aware when the plugin supports it) and enforce *act*."""
    flow = await _read_flow(session, flow_id, current_user.id)
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        await ensure_flow_permission(
            current_user,
            act,
            flow_id=flow_id,
            flow_user_id=flow.user_id,
            workspace_id=flow.workspace_id,
            folder_id=flow.folder_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, detail="Flow not found") from exc
    return flow


async def get_authorized_flow_for_read(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> Flow:
    """Return a flow the caller may read (404 when denied or missing)."""
    return await _get_authorized_flow(FlowAction.READ, flow_id=flow_id, current_user=current_user, session=session)


async def get_authorized_flow_for_write(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> Flow:
    """Return a flow the caller may write (404 when denied or missing)."""
    return await _get_authorized_flow(FlowAction.WRITE, flow_id=flow_id, current_user=current_user, session=session)


async def get_authorized_flow_for_delete(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> Flow:
    """Return a flow the caller may delete (404 when denied or missing)."""
    return await _get_authorized_flow(FlowAction.DELETE, flow_id=flow_id, current_user=current_user, session=session)


async def require_flow_create_permission(
    current_user: CurrentActiveUser,
    flow: FlowCreate,
) -> None:
    """Authorize CREATE at the destination workspace/folder before inserting a flow."""
    await ensure_flow_permission(
        current_user,
        FlowAction.CREATE,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )


AuthorizedReadFlow = Annotated[Flow, Depends(get_authorized_flow_for_read)]
AuthorizedWriteFlow = Annotated[Flow, Depends(get_authorized_flow_for_write)]
AuthorizedDeleteFlow = Annotated[Flow, Depends(get_authorized_flow_for_delete)]
RequireFlowCreate = Annotated[None, Depends(require_flow_create_permission)]
