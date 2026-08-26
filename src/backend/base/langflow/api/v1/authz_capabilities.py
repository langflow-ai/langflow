"""Discover administration permissions and optional authorization features."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/capabilities", tags=["Authorization"])


class AdministrationCapabilities(BaseModel):
    user: bool = Field(description="Caller may administer other users through user:manage.")
    team: bool = Field(description="Caller may administer teams and membership through team:manage.")
    role: bool = Field(description="Caller may administer roles and assignments through role:manage.")


class AuthorizationFeatures(BaseModel):
    team_role_assignments: bool = Field(
        description="The installed authorization service supports team-role assignments."
    )


class AuthorizationCapabilities(BaseModel):
    administration: AdministrationCapabilities
    features: AuthorizationFeatures

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "administration": {"user": True, "team": False, "role": False},
                    "features": {"team_role_assignments": False},
                }
            ]
        }
    }


@router.get("", response_model=AuthorizationCapabilities)
@router.get("/", response_model=AuthorizationCapabilities, include_in_schema=False)
async def get_authorization_capabilities(current_user: CurrentActiveUser) -> AuthorizationCapabilities:
    """Return caller-specific administration access and installed features."""
    service = get_authorization_service()
    if current_user.is_superuser:
        administration = AdministrationCapabilities(user=True, team=True, role=True)
    else:
        administration = AdministrationCapabilities(
            user=await service.can_administer(user_id=current_user.id, resource="user"),
            team=await service.can_administer(user_id=current_user.id, resource="team"),
            role=await service.can_administer(user_id=current_user.id, resource="role"),
        )
    return AuthorizationCapabilities(
        administration=administration,
        features=AuthorizationFeatures(
            team_role_assignments=await service.supports_team_role_assignments(),
        ),
    )
