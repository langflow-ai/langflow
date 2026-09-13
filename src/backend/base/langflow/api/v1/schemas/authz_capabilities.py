"""Response schema for collaboration capability discovery."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AuthorizationCapabilitiesRead(BaseModel):
    enforcement_active: bool
    service_ready: bool
    team_roles_supported: bool
    user_team_sharing_supported: bool
    share_modes: list[Literal["execute", "write"]]
    conditional_writes_required: bool
    can_administer_platform: bool
    can_create_team: bool


__all__ = ["AuthorizationCapabilitiesRead"]
