"""Fail-closed authorization helpers for identity administration routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from langflow.services.authorization.audit import AUDIT_EVENT_ACCESS, audit_decision

if TYPE_CHECKING:
    from lfx.services.authorization import AdministrationResource, BaseAuthorizationService

    from langflow.services.database.models.user.model import User, UserRead

ADMINISTRATION_DENIED_CODE = "administration_denied"
ADMINISTRATION_REQUIRED_REASON = "administration_required"


def administration_audit_details(
    details: dict | None = None,
    *,
    operation_id: str | None = None,
    source: str = "manual",
) -> dict:
    """Build the non-secret metadata common to administrative mutations.

    ``details`` keeps whatever the route already records (the audit ``event``
    family, ``status_code``/``reason`` on denials, changed field names on
    mutations). ``source`` names the origin of the request and ``operation_id``
    echoes the caller's ``X-Langflow-Operation-ID`` so a CLI run can be
    correlated across the audit trail. Secrets are never included.
    """
    result = dict(details or {})
    result["source"] = source
    if operation_id:
        result["operation_id"] = operation_id
    return result


async def is_administrator(
    user: User | UserRead,
    *,
    resource: AdministrationResource,
    authorization_service: BaseAuthorizationService,
) -> bool:
    """Return whether ``user`` is a superuser or a plugin-delegated administrator."""
    if getattr(user, "is_superuser", False):
        return True
    return await authorization_service.can_administer(user_id=user.id, resource=resource)


def administration_denied(detail: str | None = None, *, resource: AdministrationResource) -> HTTPException:
    """Build the stable 403 raised when delegated administration is refused."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail or f"Permission denied: {resource}:manage is required.",
        headers={"X-Langflow-Error-Code": ADMINISTRATION_DENIED_CODE},
    )


async def ensure_administration_permission(
    user: User | UserRead,
    *,
    resource: AdministrationResource,
    authorization_service: BaseAuthorizationService,
    action: str,
    obj: str,
    operation_id: str | None = None,
    denial_detail: str | None = None,
) -> None:
    """Allow superusers or a plugin-authorized delegated administrator.

    Denials are audited here so dependency-level checks still record the
    attempted mutation before FastAPI validates a protected request body.
    Route modules that need their own patchable audit sink should call
    :func:`is_administrator` and :func:`administration_denied` directly.
    """
    if await is_administrator(user, resource=resource, authorization_service=authorization_service):
        return
    await audit_decision(
        user_id=user.id,
        action=action,
        obj=obj,
        result="deny",
        details=administration_audit_details(
            {
                "event": AUDIT_EVENT_ACCESS,
                "status_code": status.HTTP_403_FORBIDDEN,
                "reason": ADMINISTRATION_REQUIRED_REASON,
            },
            operation_id=operation_id,
        ),
    )
    raise administration_denied(denial_detail, resource=resource)
