"""Typed contracts for ``/api/v1/authz/teams``."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

TeamRoleLiteral = Literal["admin", "maintainer", "user"]


class TeamMemberInput(BaseModel):
    """One explicit member/role requested in a roster mutation."""

    user_id: UUID
    role: TeamRoleLiteral = "user"


class TeamCreate(BaseModel):
    """Atomic team creation with its required initial roster."""

    team_name: str = Field(..., min_length=1, max_length=255)
    adom_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Administrative-domain slug, unique across all teams.",
    )
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    members: list[TeamMemberInput] = Field(default_factory=list, max_length=200)

    @field_validator("team_name", "adom_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            message = "value must not contain only whitespace"
            raise ValueError(message)
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TeamUpdate(BaseModel):
    """Atomic metadata and roster patch."""

    team_name: str | None = Field(default=None, min_length=1, max_length=255)
    adom_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    member_upserts: list[TeamMemberInput] = Field(default_factory=list, max_length=200)
    remove_member_ids: list[UUID] = Field(default_factory=list, max_length=200)

    @field_validator("team_name", "adom_name")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            message = "value must not contain only whitespace"
            raise ValueError(message)
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_optional_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TeamCapabilities(BaseModel):
    can_update: bool = False
    can_set_active: bool = False
    can_delete: bool = False
    can_add_user_member: bool = False
    can_add_privileged_member: bool = False
    can_change_roles: bool = False
    can_remove_user_member: bool = False


class TeamRead(BaseModel):
    """Team metadata plus derived, non-persisted roster/caller state."""

    id: UUID
    team_name: str
    adom_name: str
    description: str | None
    is_active: bool
    inactivation_reason: Literal["manual", "no_active_admin"] | None = None
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    active_member_count: int = 0
    active_admin_count: int = 0
    current_user_role: TeamRoleLiteral | None = None
    capabilities: TeamCapabilities = Field(default_factory=TeamCapabilities)

    model_config = {"from_attributes": True}


class TeamMemberCreate(BaseModel):
    """Manual membership creation; provenance cannot be forged by clients."""

    user_id: UUID
    role: TeamRoleLiteral = "user"


class TeamMemberRoleUpdate(BaseModel):
    role: TeamRoleLiteral


class TeamMemberRead(BaseModel):
    """Minimal roster item safe for members of the same team."""

    id: UUID
    team_id: UUID
    user_id: UUID
    display_name: str | None = None
    avatar: str | None = None
    source: str
    role: TeamRoleLiteral
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
