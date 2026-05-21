"""Pydantic schemas for the ``/api/v1/authz/shares`` router.

Mirrors the ``AuthzShare`` SQLModel but flattens the enum values to literals so
clients see a clear allow-list in the OpenAPI schema rather than the raw
SQLAlchemy enum class.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# Centralised slugs that match the Casbin object prefixes used elsewhere in
# this module. Keep this list aligned with the action-enum modules; adding a
# new shareable resource type requires touching both places.
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
    """Payload for creating an ``authz_share`` row.

    Targeted scopes (``team``, ``user``) require a ``target_id``; untargeted
    scopes (``private``, ``public``) forbid one. The DB CHECK constraint
    ``scope_target_consistency`` enforces the same shape — the validator below
    is just so the API returns 422 instead of leaking the DB error.
    """

    resource_type: ShareResourceType
    resource_id: UUID
    scope: ShareScopeLiteral
    target_id: UUID | None = Field(default=None)
    permission_level: SharePermissionLiteral = "read"

    @model_validator(mode="after")
    def _check_scope_target_consistency(self) -> ShareCreate:
        targeted = self.scope in ("team", "user")
        has_target = self.target_id is not None
        if targeted and not has_target:
            msg = f"scope={self.scope!r} requires target_id"
            raise ValueError(msg)
        if not targeted and has_target:
            msg = f"scope={self.scope!r} must not include a target_id"
            raise ValueError(msg)
        return self


class ShareUpdate(BaseModel):
    """Payload for updating an ``authz_share`` row.

    Only ``permission_level`` is editable. Changing target_id or scope means
    you wanted a different share — revoke and recreate.
    """

    permission_level: SharePermissionLiteral


class ShareRead(BaseModel):
    """Read-only projection of an ``authz_share`` row."""

    id: UUID
    resource_type: str
    resource_id: UUID
    scope: ShareScopeLiteral
    target_id: UUID | None
    permission_level: SharePermissionLiteral
    created_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
