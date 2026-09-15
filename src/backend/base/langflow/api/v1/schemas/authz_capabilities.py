"""Response schema for collaboration capability discovery."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class AuthorizationCapabilitiesRead(BaseModel):
    administration: AdministrationCapabilities
    features: AuthorizationFeatures
    enforcement_active: bool
    service_ready: bool
    team_roles_supported: bool
    user_team_sharing_supported: bool
    share_modes: list[Literal["execute", "write"]]
    conditional_writes_required: bool
    can_administer_platform: bool
    can_create_team: bool


__all__ = ["AuthorizationCapabilitiesRead"]
