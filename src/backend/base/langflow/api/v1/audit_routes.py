"""Reading the audit log for one resource.

Scoped to a single resource on purpose. An unscoped listing would have to filter
rows down to what the caller may see, and getting that filter subtly wrong leaks
somebody else's history; asking for one resource lets the resource's own
permission guard answer the question instead.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, func, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.author_names import attach_usernames
from langflow.services.audit.events import RESOURCE_FLOW
from langflow.services.audit.recorder import is_enabled
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.audit_log.model import (
    AuditLog,
    AuditLogListResponse,
    AuditLogRead,
)
from langflow.services.database.models.flow.model import Flow

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/audit", tags=["Audit"])

MAX_PAGE_SIZE = 200


async def _authorize_flow(session: AsyncSession, user: CurrentActiveUser, resource_id: UUID) -> None:
    """Refuse unless the caller may read the flow itself.

    Fetched through ``authorized_or_owner_scoped`` rather than by id alone: the
    OSS pass-through allows every permission check, so a query that is not
    owner-scoped would let anyone holding a flow's UUID read its history. A
    denial is reported as 404 so the endpoint cannot be used to probe for which
    UUIDs exist.
    """
    flow = await authorized_or_owner_scoped(
        session,
        Flow,
        id_column=Flow.id,
        resource_id=resource_id,
        owner_column=Flow.user_id,
        owner_id=user.id,
    )
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        await ensure_flow_permission(
            user,
            FlowAction.READ,
            flow_id=flow.id,
            flow_user_id=flow.user_id,
            workspace_id=flow.workspace_id,
            folder_id=flow.folder_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, detail="Flow not found") from exc


# Adding a resource to the audit log means adding its guard here, and nothing else.
AUTHORIZERS = {RESOURCE_FLOW: _authorize_flow}


@router.get("/{resource_type}/{resource_id}", response_model=AuditLogListResponse)
async def read_audit_log(
    resource_type: str,
    resource_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    event: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
) -> AuditLogListResponse:
    """Return audit rows for one resource, newest first."""
    if not is_enabled():
        raise HTTPException(status_code=404, detail="Audit log is not enabled")

    authorize = AUTHORIZERS.get(resource_type)
    if authorize is None:
        raise HTTPException(status_code=404, detail=f"No audit log for resource type {resource_type!r}")
    await authorize(session, current_user, resource_id)

    filters = [AuditLog.resource_type == resource_type, AuditLog.resource_id == resource_id]
    if event:
        filters.append(AuditLog.event == event)
    if since:
        filters.append(col(AuditLog.created_at) >= since)
    if until:
        filters.append(col(AuditLog.created_at) <= until)

    total = (await session.exec(select(func.count()).select_from(AuditLog).where(*filters))).one()
    rows = (
        await session.exec(
            select(AuditLog)
            .where(*filters)
            .order_by(col(AuditLog.created_at).desc(), col(AuditLog.id).desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    entries = [AuditLogRead.model_validate(row, from_attributes=True) for row in rows]
    await attach_usernames(session, entries)
    return AuditLogListResponse(entries=entries, total=total)
