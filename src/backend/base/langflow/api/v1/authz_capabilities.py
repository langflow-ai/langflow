"""Authenticated, non-secret authorization product capabilities."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_capabilities import (
    AdministrationCapabilities,
    AuthorizationCapabilitiesRead,
    AuthorizationFeatures,
)
from langflow.services.authorization.admin import is_administrator
from langflow.services.authorization.collaboration import (
    CollaborationCapabilityError,
    discover_collaboration_capabilities,
)
from langflow.services.authorization.fetch import authorization_admission
from langflow.services.authorization.repository import load_active_user
from langflow.services.authorization.team_management import actor_can_administer_platform
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/capabilities", tags=["Authorization"])


@router.get("", response_model=AuthorizationCapabilitiesRead, response_model_exclude_none=True)
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
        service = get_authorization_service()
        administration = AdministrationCapabilities(
            user=await is_administrator(actor, resource="user", authorization_service=service),
            team=await is_administrator(actor, resource="team", authorization_service=service),
            role=await is_administrator(actor, resource="role", authorization_service=service),
        )
        plugin_features = await service.get_feature_capabilities(
            user_id=actor.id,
            is_superuser=can_administer_platform,
        )
        directory = plugin_features.get("directory")
        features = AuthorizationFeatures(
            team_role_assignments=await service.supports_team_role_assignments(),
            directory=directory if isinstance(directory, dict) else None,
        )
    return AuthorizationCapabilitiesRead(
        administration=administration,
        features=features,
        enforcement_active=capabilities.enforcement_active,
        service_ready=capabilities.service_ready,
        team_roles_supported=capabilities.team_roles_supported,
        user_team_sharing_supported=capabilities.user_team_sharing_supported,
        share_modes=["execute", "write"] if capabilities.collaboration_ready else [],
        conditional_writes_required=capabilities.conditional_writes_required,
        can_administer_platform=can_administer_platform,
        can_create_team=administration.team and capabilities.collaboration_ready,
    )


__all__ = ["router"]
