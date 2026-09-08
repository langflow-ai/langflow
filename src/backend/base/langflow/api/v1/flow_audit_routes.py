"""Reading back who changed a flow and what they changed.

Its own route rather than a field on the flow: the trail is denser than anything
else about a flow, it is paginated, and nobody loading a canvas should pay for it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, desc, select

from langflow.api.utils import DbSession
from langflow.api.utils.author_names import attach_usernames
from langflow.api.v1.authz_route_dependencies import AuthorizedReadFlow
from langflow.services.database.models.flow_audit.model import (
    FlowAuditEntry,
    FlowAuditEntryRead,
    FlowAuditListResponse,
)
from langflow.services.flow_audit.recorder import is_enabled

router = APIRouter(prefix="/flows/{flow_id}/audit", tags=["Flows"], include_in_schema=False)

MAX_PAGE_SIZE = 200


@router.get("/", response_model=FlowAuditListResponse, status_code=200)
async def list_flow_audit_entries(
    *,
    session: DbSession,
    flow_id: UUID,  # noqa: ARG001
    flow: AuthorizedReadFlow,
    actor: Annotated[UUID | None, Query(description="Only entries written by this user")] = None,
    since: Annotated[datetime | None, Query(description="Only entries updated at or after this time")] = None,
    until: Annotated[datetime | None, Query(description="Only entries updated at or before this time")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    before: Annotated[datetime | None, Query(description="Cursor: continue from this updated_at")] = None,
) -> FlowAuditListResponse:
    """Return this flow's edit trail, newest first.

    Whoever may read the flow may read its trail: it describes changes to a graph
    they can already see in full, so a narrower rule would protect nothing.
    """
    if not is_enabled():
        raise HTTPException(
            status_code=404,
            detail="The flow audit trail is not enabled on this deployment.",
        )

    statement = select(FlowAuditEntry).where(FlowAuditEntry.flow_id == flow.id)
    if actor is not None:
        statement = statement.where(FlowAuditEntry.user_id == actor)
    if since is not None:
        statement = statement.where(col(FlowAuditEntry.updated_at) >= since)
    if until is not None:
        statement = statement.where(col(FlowAuditEntry.updated_at) <= until)
    if before is not None:
        statement = statement.where(col(FlowAuditEntry.updated_at) < before)

    rows = (await session.exec(statement.order_by(desc(col(FlowAuditEntry.updated_at))).limit(limit + 1))).all()

    has_more = len(rows) > limit
    page = rows[:limit]
    entries = list(
        await attach_usernames(session, [FlowAuditEntryRead.model_validate(row, from_attributes=True) for row in page])
    )
    next_cursor = page[-1].updated_at.isoformat() if has_more and page and page[-1].updated_at else None
    return FlowAuditListResponse(entries=entries, next_cursor=next_cursor)
