"""Pydantic schemas for /api/v1/authz/role-assignments."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoleAssignmentCreate(BaseModel):
    """Payload for assigning a role to a user."""

    user_id: UUID
    role_id: UUID
    domain_type: str = Field(
        default="global",
        description="``global``, ``org``, ``workspace`` — matches authz_role_assignment.domain_type",
    )
    domain_id: UUID | None = Field(
        default=None,
        description="Required when ``domain_type`` scopes to a specific org/workspace/project",
    )


class RoleAssignmentRead(BaseModel):
    """Serialized authz_role_assignment row returned by the API."""

    id: UUID
    user_id: UUID
    role_id: UUID
    domain_type: str
    domain_id: UUID | None
    assigned_at: datetime
    assigned_by: UUID | None

    model_config = {"from_attributes": True}
