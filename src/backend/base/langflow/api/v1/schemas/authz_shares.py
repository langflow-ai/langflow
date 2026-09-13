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
    target_name: str | None = None
    permission_level: SharePermissionLiteral
    display_mode: Literal["read", "use", "edit", "admin"] | None = None
    revision: int = Field(ge=1)
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShareAccessSourceRead(BaseModel):
    """Bounded, non-secret explanation for effective resource access."""

    kind: str
    actions: list[str]
    source_id: UUID | None = None
    label: str | None = None


class ShareEffectiveAccessRead(BaseModel):
    """Effective actions and their canonical source explanations."""

    actions: list[str]
    sources: list[ShareAccessSourceRead]


class ShareSummaryRead(BaseModel):
    """Management/read-safe summary for one flow or project."""

    resource_type: Literal["flow", "project"]
    resource_id: UUID
    display_name: str | None
    subject_user_id: UUID
    caller_is_owner: bool
    can_manage_shares: bool
    direct_grants: list[ShareRead]
    effective_access: ShareEffectiveAccessRead
    inherited_from_project: bool
    additional_access_warning: str | None = None
    legacy_public_access: bool = False
    administrative_grant_present: bool = False
    has_more: bool = False
    next_offset: int | None = None
