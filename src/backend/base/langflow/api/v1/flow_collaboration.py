"""WebSocket route for collaborative flow editing."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketException, status

from langflow.api.utils.collab.access import (
    FlowCollaborationAccessError,
    validate_flow_collaboration_access,
)
from langflow.api.utils.collab.connection import FlowCollaborationConnection
from langflow.services.deps import get_storage_service
from langflow.services.storage.service import StorageService

router = APIRouter(prefix="/flows", tags=["Flow Collaboration"])


@router.websocket("/{flow_id}/collab")
async def flow_collaboration_websocket(
    websocket: WebSocket,
    flow_id: UUID,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Collaborative editing socket endpoint."""
    await websocket.accept()

    try:
        access = await validate_flow_collaboration_access(websocket, flow_id)
    except WebSocketException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except FlowCollaborationAccessError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=exc.detail)
        return

    await FlowCollaborationConnection(
        websocket=websocket,
        flow_id=flow_id,
        current_user=access.current_user,
        storage_service=storage_service,
    ).run(starting_revision=access.starting_revision)
