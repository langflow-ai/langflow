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
from langflow.services.audit.vocabulary import AuditEventType, AuditOperation, AuditResourceType, AuditResult
from langflow.services.authorization import ensure_flow_audit_read_permission
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.database.models.flow.model import Flow

router = APIRouter(prefix="/flows", tags=["Flows"])

_FLOW_OPERATIONS = frozenset(
    {AuditOperation.CREATE, AuditOperation.REPLACE, AuditOperation.PATCH, AuditOperation.DELETE}
)
_INITIAL_EVENT_TYPES = frozenset({AuditEventType.ACTION})
_INITIAL_RESULTS = frozenset({AuditResult.SUCCEEDED, AuditResult.FAILED})


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
    query = parse_audit_query(
        request,
        resource_type=AuditResourceType.FLOW,
        id_param="flow_id",
        allowed_operations=_FLOW_OPERATIONS,
        allowed_event_types=_INITIAL_EVENT_TYPES,
        allowed_results=_INITIAL_RESULTS,
    )
    flow_id = query.filters.resource_id
    # Only the guard's three columns: loading the row would pull the whole graph
    # JSON into memory to answer a page of small audit rows.
    scope = (
        (await session.exec(select(Flow.user_id, Flow.workspace_id, Flow.folder_id).where(Flow.id == flow_id))).first()
        if flow_id is not None
        else None
    )
    flow_user_id, workspace_id, folder_id = scope if scope is not None else (None, None, None)
    await ensure_flow_audit_read_permission(
        current_user,
        flow_id=flow_id,
        flow_user_id=flow_user_id,
        workspace_id=workspace_id,
        folder_id=folder_id,
    )
    visibility = await owner_visibility(current_user, select(Flow.id).where(Flow.user_id == current_user.id))
    page = await read_audit_page(session, query, visibility)
    return FlowAuditPage(items=[_flow_item(event) for event in page.items], next_cursor=page.next_cursor)
