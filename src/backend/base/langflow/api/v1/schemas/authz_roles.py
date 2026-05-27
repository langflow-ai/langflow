"""Pydantic schemas for /api/v1/authz/roles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    """Payload for creating an authz_role row."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None)
    permissions: list[str] = Field(
        default_factory=list,
        description=(
            "Permission strings in the form ``<resource_type>:<obj_pattern>:<action>`` — "
            "for example ``flow:*:read``, ``deployment:*:execute``. Plugin (e.g. enterprise "
            "Casbin) is responsible for compiling these to its policy format."
        ),
    )
    parent_role_id: UUID | None = Field(default=None)


class RoleUpdate(BaseModel):
    """Payload for updating an authz_role row (PATCH semantics — only set fields apply)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    permissions: list[str] | None = None
    parent_role_id: UUID | None = None


class RoleRead(BaseModel):
    """Serialized authz_role row returned by the API."""

    id: UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]
    parent_role_id: UUID | None
    workspace_id: UUID | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None

    model_config = {"from_attributes": True}
