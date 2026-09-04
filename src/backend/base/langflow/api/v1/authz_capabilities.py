"""Discover administration permissions and optional authorization features."""

from __future__ import annotations

from typing import Any

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
    directory: dict[str, Any] | None = Field(
        default=None,
        description="Caller-specific directory actions advertised by an installed plugin.",
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


@router.get("", response_model=AuthorizationCapabilities, response_model_exclude_none=True)
@router.get(
    "/",
    response_model=AuthorizationCapabilities,
    response_model_exclude_none=True,
    include_in_schema=False,
)
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
    plugin_features = await service.get_feature_capabilities(
        user_id=current_user.id,
        is_superuser=current_user.is_superuser,
    )
    directory = plugin_features.get("directory")
    return AuthorizationCapabilities(
        administration=administration,
        features=AuthorizationFeatures(
            team_role_assignments=await service.supports_team_role_assignments(),
            directory=directory if isinstance(directory, dict) else None,
        ),
    )
