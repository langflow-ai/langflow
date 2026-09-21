"""``GET /api/v1/projects/audits``: a read-only, Project-specific view over ``audit_events``.

It never returns Project or Flow content, and reading it records no event.
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
from langflow.services.authorization import ensure_project_audit_read_permission
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.database.models.folder.model import Folder

router = APIRouter(prefix="/projects", tags=["Projects"])

_PROJECT_OPERATIONS = frozenset(
    {AuditOperation.CREATE, AuditOperation.REPLACE, AuditOperation.PATCH, AuditOperation.DELETE}
)
_INITIAL_EVENT_TYPES = frozenset({AuditEventType.ACTION})
_INITIAL_RESULTS = frozenset({AuditResult.SUCCEEDED, AuditResult.FAILED})


class ProjectAuditEventRead(AuditEventReadBase):
    project_id: UUID
    project_name: str | None


class ProjectAuditPage(BaseModel):
    items: list[ProjectAuditEventRead]
    next_cursor: str | None


def _project_item(event: AuditEvent) -> ProjectAuditEventRead:
    return ProjectAuditEventRead(project_id=event.resource_id, project_name=event.resource_name, **base_fields(event))


@router.get(
    "/audits",
    response_model=ProjectAuditPage,
    openapi_extra={"parameters": openapi_parameters("project_id", "Exact Project.")},
)
async def read_project_audits(
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> ProjectAuditPage:
    """Project audit events, newest first, filtered and keyset-paginated.

    Requires the ``project:audit_read`` permission. Without an authorization plugin,
    a non-superuser sees events on Projects they own and events they made.
    """
    query = parse_audit_query(
        request,
        resource_type=AuditResourceType.PROJECT,
        id_param="project_id",
        allowed_operations=_PROJECT_OPERATIONS,
        allowed_event_types=_INITIAL_EVENT_TYPES,
        allowed_results=_INITIAL_RESULTS,
    )
    project_id = query.filters.resource_id
    project = await session.get(Folder, project_id) if project_id is not None else None
    await ensure_project_audit_read_permission(
        current_user,
        project_id=project_id,
        project_user_id=getattr(project, "user_id", None),
        workspace_id=getattr(project, "workspace_id", None),
    )
    visibility = await owner_visibility(current_user, select(Folder.id).where(Folder.user_id == current_user.id))
    page = await read_audit_page(session, query, visibility)
    return ProjectAuditPage(items=[_project_item(event) for event in page.items], next_cursor=page.next_cursor)
