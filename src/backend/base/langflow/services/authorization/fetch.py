"""Share-aware fetch helpers for authorization-guarded routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from fastapi import HTTPException, status
from sqlmodel import select

from langflow.services.deps import get_authorization_service

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
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
    for_update: bool = False,
) -> T | None:
    """Load by id when cross-user fetch is supported; otherwise scope by owner.

    ``for_update`` refreshes any identity-map instance from the database and
    locks the selected row through the caller's transaction. Write paths use
    this to keep authorization of the current scope atomic with the mutation.
    """
    authz = get_authorization_service()
    # Require both plugin capability and AUTHZ_ENABLED before widening the query.
    if await authz.supports_cross_user_fetch() and await authz.is_enabled():
        stmt = select(model).where(id_column == resource_id)
    else:
        stmt = select(model).where(id_column == resource_id).where(owner_column == owner_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return (await session.exec(stmt)).first()


def deny_to_404(exc: HTTPException, detail: str = "Not found") -> HTTPException:
    """Map a 403 permission-deny to 404 (UUID privacy); return any other error unchanged."""
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    # Never relabel a non-403 (e.g. 4xx/5xx) as "not found"; surface it unchanged.
    return exc


async def deny_to_404_unless_readable(
    exc: HTTPException,
    read_check: Callable[[], Awaitable[None]],
    *,
    denied_detail: str,
    not_found_detail: str = "Not found",
) -> HTTPException:
    """Answer a denied action honestly when the caller can already read the resource.

    The 404 mask exists so a caller cannot probe UUIDs they have no access to.
    It buys nothing once the caller has read the resource — they already know it
    exists — and it costs them a truthful answer: "not found" sends someone to
    debug an identifier that is correct, when the real answer is that they lack
    a permission. So: readable -> 403 with ``denied_detail``, unreadable ->
    404 with ``not_found_detail``.

    ``read_check`` must raise ``HTTPException`` when the caller may not read.
    Only a 403 means "cannot see it"; any other status from either the original
    denial or the read check is a different answer entirely -- a 503 from the
    authorization plugin says the decision is unavailable, not that the resource
    is missing -- and is surfaced unchanged rather than relabelled.
    """
    if exc.status_code != status.HTTP_403_FORBIDDEN:
        return exc
    try:
        await read_check()
    except HTTPException as read_exc:
        if read_exc.status_code != status.HTTP_403_FORBIDDEN:
            # Reporting a service failure as "not found" hides an outage behind
            # a routine-looking response and sends the caller to check their id.
            return read_exc
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=denied_detail)
