"""``GET /api/v1/flows/audits``: a read-only, Flow-specific view over ``audit_events``.

It never returns Flow content, and reading it records no event.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.audit_reads import (
    AuditEventReadBase,
    base_fields,
    openapi_parameters,
    owner_visibility,
    parse_audit_query,
    read_audit_page,
)
from langflow.services.audit.vocabulary import AuditResourceType
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.database.models.flow.model import Flow

router = APIRouter(prefix="/flows", tags=["Flows"])


class FlowAuditEventRead(AuditEventReadBase):
    flow_id: UUID
    flow_name: str | None


class FlowAuditPage(BaseModel):
    items: list[FlowAuditEventRead]
    next_cursor: str | None


def _flow_item(event: AuditEvent) -> FlowAuditEventRead:
    return FlowAuditEventRead(flow_id=event.resource_id, flow_name=event.resource_name, **base_fields(event))


@router.get(
    "/audits",
    response_model=FlowAuditPage,
    openapi_extra={"parameters": openapi_parameters("flow_id", "Exact Flow.")},
)
async def read_flow_audits(
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> FlowAuditPage:
    """Flow audit events, newest first, filtered and keyset-paginated.

    Requires the ``flow:audit_read`` permission. Without an authorization plugin,
    a non-superuser sees events on Flows they own and events they made.
    """
    query = parse_audit_query(request, resource_type=AuditResourceType.FLOW, id_param="flow_id")
    flow_id = query.filters.resource_id
    flow = await session.get(Flow, flow_id) if flow_id is not None else None
    await ensure_flow_permission(
        current_user,
        FlowAction.AUDIT_READ,
        flow_id=flow_id,
        flow_user_id=getattr(flow, "user_id", None),
        workspace_id=getattr(flow, "workspace_id", None),
        folder_id=getattr(flow, "folder_id", None),
    )
    visibility = await owner_visibility(current_user, select(Flow.id).where(Flow.user_id == current_user.id))
    page = await read_audit_page(session, query, visibility)
    return FlowAuditPage(items=[_flow_item(event) for event in page.items], next_cursor=page.next_cursor)
