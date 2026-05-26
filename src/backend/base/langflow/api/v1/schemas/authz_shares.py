"""Pydantic schemas for /api/v1/authz/shares."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# Shareable resource slugs (keep aligned with authorization action modules).
ShareResourceType = Literal[
    "flow",
    "deployment",
    "project",
    "knowledge_base",
    "variable",
    "file",
]

ShareScopeLiteral = Literal["private", "team", "user", "public"]
SharePermissionLiteral = Literal["read", "write", "execute", "admin"]


class ShareCreate(BaseModel):
    """Payload for creating an authz_share row."""

    resource_type: ShareResourceType
    resource_id: UUID
    scope: ShareScopeLiteral
    target_id: UUID | None = Field(default=None)
    permission_level: SharePermissionLiteral = "read"

    @model_validator(mode="after")
    def _check_scope_target_consistency(self) -> ShareCreate:
        """Require target_id for user/team scopes; forbid it for private/public."""
        targeted = self.scope in ("team", "user")
        if targeted and self.target_id is None:
            msg = f"scope {self.scope!r} requires target_id"
            raise ValueError(msg)
        if not targeted and self.target_id is not None:
            msg = f"scope {self.scope!r} must not set target_id"
            raise ValueError(msg)
        return self


class ShareUpdate(BaseModel):
    """Payload for updating an authz_share permission level."""

    permission_level: SharePermissionLiteral


class ShareRead(BaseModel):
    """Serialized authz_share row returned by the API."""

    id: UUID
    resource_type: ShareResourceType
    resource_id: UUID
    scope: ShareScopeLiteral
    target_id: UUID | None
    permission_level: SharePermissionLiteral
    created_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
