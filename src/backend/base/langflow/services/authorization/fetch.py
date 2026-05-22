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

List-endpoint SQL prefilter
---------------------------

:func:`share_visibility_filter` returns a SQLAlchemy boolean expression that
list-endpoint queries AND into their base ``select(...)`` so paginated
results' ``page.total`` is accurate. The expression is a floor — owner +
``access_type=PUBLIC`` (when applicable) + ``authz_share``-backed visibility
— never widening past what an enterprise plugin could grant. The plugin
still adds the ceiling via the existing :func:`filter_visible_resources`
post-pass on the page's items.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlmodel import col, select

from langflow.services.database.models.auth.authz import (
    AuthzShare,
    AuthzTeamMember,
    SharePermissionLevel,
    ShareScope,
)
from langflow.services.deps import get_authorization_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from sqlalchemy.orm.attributes import InstrumentedAttribute
    from sqlalchemy.sql import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T")


# Default permission levels that satisfy a list-read visibility check. READ is
# the floor; higher levels imply read access, so any share grant at READ or
# above lets the recipient see the resource in their list view.
_READ_PERMISSION_LEVELS: tuple[str, ...] = (
    SharePermissionLevel.READ.value,
    SharePermissionLevel.WRITE.value,
    SharePermissionLevel.EXECUTE.value,
    SharePermissionLevel.ADMIN.value,
)


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


def share_visibility_filter(
    user: Any,
    *,
    resource_type: str,
    id_column: InstrumentedAttribute,
    owner_column: InstrumentedAttribute,
    access_type_column: InstrumentedAttribute | None = None,
    public_value: Any = None,
    permission_levels: Iterable[str] = _READ_PERMISSION_LEVELS,
) -> ColumnElement[bool]:
    """Return a SQL predicate selecting resources the user can read.

    Plumbing for list endpoints: callers ``select(Resource).where(
    share_visibility_filter(...))`` so paginated queries get accurate
    ``page.total`` counts. Works as a *floor*:

    * ``AUTHZ_ENABLED=false`` → returns ``owner_column == user.id`` so list
      behavior matches the pre-authz contract exactly. No share rows are
      consulted; enabling sharing requires AUTHZ to be on.
    * ``AUTHZ_ENABLED=true`` → ORs together owner ownership, optional
      ``access_type == public_value`` (when the resource supports a public
      flag), and ``authz_share``-backed visibility (scope=public,
      scope=user/target=user.id, scope=team/target IN <user's teams>).

    The optional ``filter_visible_resources`` post-pass remains the ceiling
    for plugin-only grants (e.g. Casbin role-based access that doesn't have
    a matching share row).

    Parameters
    ----------
    user:
        Active user-like with an ``id`` attribute (UUID).
    resource_type:
        ``authz_share.resource_type`` string (``"flow"``, ``"deployment"``,
        ``"project"``, etc.).
    id_column:
        SQLAlchemy column attribute for the resource's primary key
        (e.g. ``Flow.id``).
    owner_column:
        SQLAlchemy column attribute for the resource's owner FK
        (e.g. ``Flow.user_id``).
    access_type_column:
        Optional column attribute carrying a PUBLIC/PRIVATE-style flag
        (e.g. ``Flow.access_type``). When provided, rows where this column
        equals ``public_value`` are unconditionally included.
    public_value:
        Value of ``access_type_column`` that marks a row as publicly
        readable. Required when ``access_type_column`` is set.
    permission_levels:
        ``authz_share.permission_level`` values that count as "can read".
        Defaults to the read-or-above ladder.
    """
    user_id: UUID = user.id  # let attribute access raise — callers always pass a user.

    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED:
        # Matches the pre-authz owner-scoped query exactly. Returning a
        # ``ColumnElement`` (rather than a plain bool) so callers can compose
        # this expression with other WHERE clauses unconditionally.
        return owner_column == user_id

    # Subquery: resource ids the user can read via authz_share. Three OR
    # branches matching ShareScope semantics; AUTHZ_ENABLED=true is the
    # precondition for any of them to fire.
    team_member_subquery = select(AuthzTeamMember.team_id).where(AuthzTeamMember.user_id == user_id)
    share_subquery = select(AuthzShare.resource_id).where(
        AuthzShare.resource_type == resource_type,
        col(AuthzShare.permission_level).in_(tuple(permission_levels)),
        or_(
            AuthzShare.scope == ShareScope.PUBLIC.value,
            (AuthzShare.scope == ShareScope.USER.value) & (AuthzShare.target_id == user_id),
            (AuthzShare.scope == ShareScope.TEAM.value) & col(AuthzShare.target_id).in_(team_member_subquery),
        ),
    )

    clauses: list[ColumnElement[bool]] = [
        owner_column == user_id,
        col(id_column).in_(share_subquery),
    ]
    if access_type_column is not None:
        if public_value is None:
            msg = "share_visibility_filter: public_value must be provided when access_type_column is set"
            raise ValueError(msg)
        clauses.insert(1, access_type_column == public_value)

    return or_(*clauses)


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
