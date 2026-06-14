"""Share-aware fetch helpers for authorization-guarded routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from fastapi import HTTPException, status
from sqlmodel import select

from langflow.services.deps import get_authorization_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm.attributes import InstrumentedAttribute
    from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T")


async def authorized_or_owner_scoped(
    session: AsyncSession,
    model: type[T],
    *,
    id_column: InstrumentedAttribute,
    resource_id: UUID,
    owner_column: InstrumentedAttribute,
    owner_id: UUID,
) -> T | None:
    """Load by id when cross-user fetch is supported; otherwise scope by owner."""
    authz = get_authorization_service()
    # Require both plugin capability and AUTHZ_ENABLED before widening the query.
    if await authz.supports_cross_user_fetch() and await authz.is_enabled():
        stmt = select(model).where(id_column == resource_id)
    else:
        stmt = select(model).where(id_column == resource_id).where(owner_column == owner_id)
    return (await session.exec(stmt)).first()


def deny_to_404(exc: HTTPException, detail: str = "Not found") -> HTTPException:
    """Map a 403 permission-deny to 404 (UUID privacy); return any other error unchanged."""
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    # Never relabel a non-403 (e.g. 4xx/5xx) as "not found"; surface it unchanged.
    return exc
