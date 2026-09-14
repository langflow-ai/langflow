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
from langflow.services.audit.events import RESOURCE_FLOW, RESOURCE_PROJECT
from langflow.services.audit.recorder import is_enabled
from langflow.services.authorization import (
    FlowAction,
    ProjectAction,
    ensure_flow_permission,
    ensure_project_permission,
)
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.audit_event.model import (
    AuditEvent,
    AuditEventListResponse,
    AuditEventRead,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/audit", tags=["Audit"])

MAX_PAGE_SIZE = 200


async def _authorize_by_trail(
    session: AsyncSession,
    user: CurrentActiveUser,
    resource_type: str,
    resource_id: UUID,
    *,
    detail: str,
) -> None:
    """Fall back to the trail's own attribution once the resource is gone.

    Costs one indexed query per unauthorized request, which is the price of
    answering 404 without confirming whether the UUID ever existed. Accepted
    deliberately: the endpoint is session-authenticated, so probing is already
    bounded by holding an account. Exposing it more widely would want a rate
    limit before this query.
    """
    acted = (
        await session.exec(
            select(AuditEvent.id).where(
                AuditEvent.resource_type == resource_type,
                AuditEvent.resource_id == resource_id,
                AuditEvent.user_id == user.id,
            )
        )
    ).first()
    if acted is None:
        raise HTTPException(status_code=404, detail=detail)


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
        # A deleted flow is exactly the one somebody asks about later, so its
        # trail outlives it: with no row left to authorize against, the trail's
        # own attribution decides, and a stranger still gets the same 404.
        await _authorize_by_trail(session, user, RESOURCE_FLOW, resource_id, detail="Flow not found")
        return
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


async def _authorize_project(session: AsyncSession, user: CurrentActiveUser, resource_id: UUID) -> None:
    """Refuse unless the caller may read the project itself.

    A deleted project is exactly the one somebody asks about later, so its trail
    has to outlive it: when the row is gone the owner recorded on the trail
    decides, and a stranger still gets the same 404 as for a project that never
    existed.
    """
    project = await authorized_or_owner_scoped(
        session,
        Folder,
        id_column=Folder.id,
        resource_id=resource_id,
        owner_column=Folder.user_id,
        owner_id=user.id,
    )
    if project is None:
        await _authorize_by_trail(session, user, RESOURCE_PROJECT, resource_id, detail="Project not found")
        return
    try:
        await ensure_project_permission(
            user,
            ProjectAction.READ,
            project_id=project.id,
            project_user_id=project.user_id,
            workspace_id=project.workspace_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, detail="Project not found") from exc


# Adding a resource to the audit log means adding its guard here, and nothing else.
AUTHORIZERS = {RESOURCE_FLOW: _authorize_flow, RESOURCE_PROJECT: _authorize_project}


@router.get("/{resource_type}/{resource_id}", response_model=AuditEventListResponse)
async def read_audit_event(
    resource_type: str,
    resource_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    event: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
) -> AuditEventListResponse:
    """Return audit rows for one resource, newest first."""
    if not is_enabled():
        raise HTTPException(status_code=404, detail="Audit log is not enabled")

    authorize = AUTHORIZERS.get(resource_type)
    if authorize is None:
        raise HTTPException(status_code=404, detail=f"No audit log for resource type {resource_type!r}")
    await authorize(session, current_user, resource_id)

    filters = [AuditEvent.resource_type == resource_type, AuditEvent.resource_id == resource_id]
    if event:
        filters.append(AuditEvent.event == event)
    if since:
        filters.append(col(AuditEvent.created_at) >= since)
    if until:
        filters.append(col(AuditEvent.created_at) <= until)

    total = (await session.exec(select(func.count()).select_from(AuditEvent).where(*filters))).one()
    rows = (
        await session.exec(
            select(AuditEvent)
            .where(*filters)
            .order_by(col(AuditEvent.created_at).desc(), col(AuditEvent.id).desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    entries = [AuditEventRead.model_validate(row, from_attributes=True) for row in rows]
    await attach_usernames(session, entries)
    return AuditEventListResponse(entries=entries, total=total)
