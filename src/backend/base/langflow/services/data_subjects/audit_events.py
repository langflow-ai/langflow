"""The dsar:* audit trail. Details carry request metadata and counts only, never the subject's identity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.services.authorization.audit import AUDIT_ACTOR_USER, audit_decision, stage_audit_decision
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

ACTION_REQUEST = "dsar:request"
ACTION_WITHDRAW = "dsar:withdraw"
ACTION_APPROVE = "dsar:approve"
ACTION_REFUSE = "dsar:refuse"
ACTION_FIND = "dsar:find"
ACTION_EXPORT = "dsar:export"
ACTION_ERASE = "dsar:erase"
RESOURCE_TYPE = "data_subject_request"


async def record_dsar_event(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    action: str,
    request_id: UUID | None,
    result: str = "allow",
    details: dict[str, Any] | None = None,
) -> None:
    """Stage the event in ``session`` so it commits (or rolls back) with the change it records."""
    auth_settings = get_settings_service().auth_settings
    obj = f"{RESOURCE_TYPE}:{request_id}" if request_id else f"{RESOURCE_TYPE}:*"
    if getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", False):
        staged = stage_audit_decision(
            session=session, user_id=actor_id, action=action, obj=obj, result=result, details=details
        )
        if not staged:
            await audit_decision(user_id=actor_id, action=action, obj=obj, result=result, details=details)
        return
    session.add(
        AuthzAuditLog(
            user_id=actor_id,
            actor_type=AUDIT_ACTOR_USER if actor_id else None,
            actor_id=actor_id,
            action=action,
            resource_type=RESOURCE_TYPE,
            resource_id=request_id,
            result=result,
            details=details,
        )
    )
