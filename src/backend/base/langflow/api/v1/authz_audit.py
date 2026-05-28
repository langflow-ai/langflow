"""Admin-only query endpoint for the ``authz_audit_log`` table.

The OSS guards write a row per authorization decision (allow / deny /
owner_override). Without a read API operators have to query the DB by hand to
investigate "why was this denied?" — this router exposes the table behind a
superuser-only filter surface so support and compliance flows can use it
without direct DB access.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import col, select

from langflow.api.utils import DbSession
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.user.model import User

router = APIRouter(prefix="/authz/audit", tags=["Authorization"])

_MAX_PAGE_SIZE = 200


class AuthzAuditLogRead(BaseModel):
    """Read-only projection of an ``AuthzAuditLog`` row."""

    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: UUID | None
    result: str
    details: dict | None
    timestamp: datetime

    model_config = {"from_attributes": True}


class AuthzAuditPage(BaseModel):
    """Paginated audit-log response."""

    items: list[AuthzAuditLogRead]
    total: int
    page: int
    size: int
    pages: int


@router.get("", response_model=AuthzAuditPage)
@router.get("/", response_model=AuthzAuditPage)
async def list_audit_log(
    session: DbSession,
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    user_id: Annotated[UUID | None, Query(description="Filter by acting user id.")] = None,
    resource_type: Annotated[
        str | None,
        Query(description="Filter by resource type slug, e.g. ``flow`` or ``deployment``."),
    ] = None,
    resource_id: Annotated[UUID | None, Query(description="Filter by resource UUID.")] = None,
    action: Annotated[
        str | None,
        Query(description="Filter by action string, e.g. ``flow:read`` or ``share:create``."),
    ] = None,
    result: Annotated[
        str | None,
        Query(description="Filter by decision result (``allow`` / ``deny`` / ``owner_override``)."),
    ] = None,
    since: Annotated[datetime | None, Query(description="Inclusive lower bound on ``timestamp``.")] = None,
    until: Annotated[datetime | None, Query(description="Exclusive upper bound on ``timestamp``.")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = 50,
) -> AuthzAuditPage:
    """Return a paginated slice of the audit log filtered by the given query params.

    Superuser only. The composite indexes on ``(user_id, timestamp)`` and
    ``(resource_type, resource_id)`` keep both "show me events for user X"
    and "show me events on resource Y" fast at scale.
    """
    if since is not None and until is not None and since >= until:
        raise HTTPException(status_code=400, detail="`since` must be strictly less than `until`")

    base = select(AuthzAuditLog)
    if user_id is not None:
        base = base.where(AuthzAuditLog.user_id == user_id)
    if resource_type is not None:
        base = base.where(AuthzAuditLog.resource_type == resource_type)
    if resource_id is not None:
        base = base.where(AuthzAuditLog.resource_id == resource_id)
    if action is not None:
        base = base.where(AuthzAuditLog.action == action)
    if result is not None:
        base = base.where(AuthzAuditLog.result == result)
    if since is not None:
        base = base.where(AuthzAuditLog.timestamp >= since)
    if until is not None:
        base = base.where(AuthzAuditLog.timestamp < until)

    # Two queries: one COUNT(*) for pagination metadata, one for the page
    # window itself. SQLAlchemy's func.count is preferred over len(rows) so
    # we don't materialise the full result set when the user just wants
    # page 1 of many.
    from sqlalchemy import func

    total_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.exec(total_stmt)).first() or 0)

    page_stmt = base.order_by(col(AuthzAuditLog.timestamp).desc()).offset((page - 1) * size).limit(size)
    rows = list(await session.exec(page_stmt))

    items = [AuthzAuditLogRead.model_validate(row, from_attributes=True) for row in rows]
    pages = (total + size - 1) // size if total > 0 else 0

    return AuthzAuditPage(items=items, total=total, page=page, size=size, pages=pages)


__all__ = ["AuthzAuditLogRead", "AuthzAuditPage", "router"]
