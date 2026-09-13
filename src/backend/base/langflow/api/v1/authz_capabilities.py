"""Authenticated, non-secret authorization product capabilities."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_capabilities import AuthorizationCapabilitiesRead
from langflow.services.authorization.collaboration import (
    CollaborationCapabilityError,
    discover_collaboration_capabilities,
)
from langflow.services.authorization.fetch import authorization_admission
from langflow.services.authorization.repository import load_active_user
from langflow.services.authorization.team_management import actor_can_administer_platform

router = APIRouter(prefix="/authz/capabilities", tags=["Authorization"])


@router.get("", response_model=AuthorizationCapabilitiesRead)
@router.get("/", response_model=AuthorizationCapabilitiesRead, include_in_schema=False)
async def get_authorization_capabilities(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> AuthorizationCapabilitiesRead:
    """Report only behavior implemented by the registered, ready service."""
    async with authorization_admission(session) as admission:
        # Authentication can create the identity in this request's transaction.
        actor = await load_active_user(admission, current_user.id)
        if actor is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        try:
            capabilities = await discover_collaboration_capabilities()
        except CollaborationCapabilityError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "AUTHORIZATION_NOT_READY", "message": "Authorization is not ready."},
            ) from exc

        can_administer_platform = actor_can_administer_platform(actor)
    return AuthorizationCapabilitiesRead(
        enforcement_active=capabilities.enforcement_active,
        service_ready=capabilities.service_ready,
        team_roles_supported=capabilities.team_roles_supported,
        user_team_sharing_supported=capabilities.user_team_sharing_supported,
        share_modes=["execute", "write"] if capabilities.collaboration_ready else [],
        conditional_writes_required=capabilities.conditional_writes_required,
        can_administer_platform=can_administer_platform,
        can_create_team=can_administer_platform and capabilities.collaboration_ready,
    )


__all__ = ["router"]
