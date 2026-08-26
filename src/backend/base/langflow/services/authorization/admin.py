"""Fail-closed authorization helpers for identity administration routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from langflow.services.authorization.audit import audit_decision

if TYPE_CHECKING:
    from lfx.services.authorization import AdministrationResource, BaseAuthorizationService

    from langflow.services.database.models.user.model import User, UserRead


def administration_audit_details(
    details: dict | None = None,
    *,
    operation_id: str | None = None,
    source: str = "manual",
) -> dict:
    """Build the non-secret metadata common to administrative mutations."""
    result = dict(details or {})
    result["source"] = source
    if operation_id:
        result["operation_id"] = operation_id
    return result


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
    """
    if user.is_superuser or await authorization_service.can_administer(user_id=user.id, resource=resource):
        return
    await audit_decision(
        user_id=user.id,
        action=action,
        obj=obj,
        result="deny",
        details=administration_audit_details(operation_id=operation_id),
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=denial_detail or f"Permission denied: {resource}:manage is required.",
        headers={"X-Langflow-Error-Code": "administration_denied"},
    )
