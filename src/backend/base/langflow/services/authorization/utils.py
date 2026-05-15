"""Authorization helpers for API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

from langflow.services.deps import get_authorization_service, get_settings_service

if TYPE_CHECKING:
    from uuid import UUID

    from langflow.services.auth.exceptions import InsufficientPermissionsError
    from langflow.services.database.models.user.model import User, UserRead


def _auth_context(user: User | UserRead) -> dict[str, Any]:
    return {"is_superuser": getattr(user, "is_superuser", False)}


async def ensure_permission(
    user: User | UserRead,
    *,
    domain: str,
    obj: str,
    act: str,
    context: dict[str, Any] | None = None,
) -> None:
    """Raise HTTP 403 if the user is not allowed to perform the action."""
    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED:
        return

    authz = get_authorization_service()
    merged_context = {**_auth_context(user), **(context or {})}
    allowed = await authz.enforce(
        user_id=user.id,
        domain=domain,
        obj=obj,
        act=act,
        context=merged_context,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {act} on {obj}",
        )


async def ensure_flow_permission(
    user: User | UserRead,
    act: str,
    *,
    flow_id: UUID | None = None,
    flow_user_id: UUID | None = None,
    domain: str = "*",
) -> None:
    """Check flow-scoped permission (e.g. flow:read, flow:write)."""
    obj = f"flow:{flow_id}" if flow_id else "flow:*"
    await ensure_permission(
        user,
        domain=domain,
        obj=obj,
        act=act,
        context={"flow_user_id": flow_user_id},
    )


def permission_denied_to_http(exc: InsufficientPermissionsError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message)
