"""Share-aware fetch helpers for guarded resource routes.

Phase 3 contract
----------------

Before Phase 3, route fetch helpers (``_read_flow``, ``get_flow_for_api_key_user``,
``get_deployment_db``, project reads in ``projects.py``) filtered every query by
``current_user.id``. That meant an enterprise plugin with a valid share grant
on a non-owned flow still saw 404 at the fetch layer before the route guard
could authorize the request.

These helpers fix that by branching on
:meth:`BaseAuthorizationService.supports_cross_user_fetch`:

* When the registered service reports ``True`` (enterprise Casbin), the row
  is loaded by id alone. The route then invokes ``ensure_*_permission`` and
  converts a plugin deny to **404** via :func:`deny_to_404` so non-shareholders
  cannot probe UUIDs.
* When the registered service reports ``False`` (OSS pass-through default),
  the helper keeps the existing owner-scoped query. That preserves the
  strict-pass-through guarantee: enabling ``LANGFLOW_AUTHZ_ENABLED=true``
  without an enterprise plugin must not silently widen cross-user visibility.
"""

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
    """Load a row by id when share-aware fetch is supported, else scope by owner.

    Parameters
    ----------
    session : AsyncSession
        Active SQLAlchemy async session.
    model : type[T]
        SQLModel class to select from.
    id_column : InstrumentedAttribute
        Primary-key column attribute (e.g. ``Flow.id``).
    resource_id : UUID
        Primary-key value to look up.
    owner_column : InstrumentedAttribute
        Owner FK column attribute (e.g. ``Flow.user_id``).
    owner_id : UUID
        Caller's user id, used when the service does not support cross-user fetch.

    Returns:
    -------
    The row, or ``None`` if no row matched. Routes should still raise 404 on
    ``None`` exactly as they did before.
    """
    authz = get_authorization_service()
    # Cross-user fetch requires BOTH the plugin capability AND enforcement
    # to be enabled. If ``AUTHZ_ENABLED=false`` the route guards are no-ops
    # (see ``ensure_permission``), so widening the fetch would let an
    # enterprise plugin's capability silently expose other users' resources
    # without any policy check. Gate on both.
    if await authz.supports_cross_user_fetch() and await authz.is_enabled():
        stmt = select(model).where(id_column == resource_id)
    else:
        stmt = select(model).where(id_column == resource_id).where(owner_column == owner_id)
    return (await session.exec(stmt)).first()


def deny_to_404(exc: HTTPException, detail: str = "Not found") -> HTTPException:
    """Convert a 403 from ``ensure_*_permission`` into a 404 for UUID privacy.

    For 403s, returns a fresh ``HTTPException(404, detail=detail)``.

    For non-403s, returns the original exception with its ``detail`` replaced
    by the caller-supplied ``detail`` and any ``headers`` dropped. This
    sanitisation is conservative on purpose: helper callers are guard sites,
    so the exception about to propagate has been filtered through an authz
    plugin whose detail string may quote resource UUIDs, owner ids, or
    policy tuples. Letting that detail land in the client response would
    leak information about resources the caller is not authorised to see.
    Routes that need to expose a richer detail (e.g. a 409 with a real
    conflict message) should catch and re-raise outside ``deny_to_404``.
    """
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return HTTPException(status_code=exc.status_code, detail=detail)
