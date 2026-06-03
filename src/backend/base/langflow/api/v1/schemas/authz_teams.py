"""Pydantic schemas for /api/v1/authz/teams and team members."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    """Payload for creating an authz_team."""

    team_name: str = Field(..., min_length=1, max_length=255)
    adom_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Administrative-domain slug, unique across all teams (often the SSO group name).",
    )
    description: str | None = None
    is_active: bool = True


class TeamUpdate(BaseModel):
    """Payload for updating an authz_team (PATCH semantics)."""

    team_name: str | None = Field(default=None, min_length=1, max_length=255)
    adom_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class TeamRead(BaseModel):
    """Serialized authz_team row returned by the API."""

    id: UUID
    team_name: str
    adom_name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamMemberCreate(BaseModel):
    """Payload for adding a user to a team."""

    user_id: UUID
    source: Literal["manual", "sso"] = "manual"


class TeamMemberRead(BaseModel):
    """Serialized authz_team_member row."""

    id: UUID
    team_id: UUID
    user_id: UUID
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
