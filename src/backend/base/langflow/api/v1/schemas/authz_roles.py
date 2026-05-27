"""Pydantic schemas for /api/v1/authz/roles."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Canonical permission slug is ``<resource>:<action>`` — matches the
# system-role seed in ``8d3a1f9c2e0b_seed_authz_system_roles`` and the
# ``"{resource}:{action}"`` contract documented in AGENTS.md. Plugins
# that compile these to policy rows expect this exact shape, so we
# reject other forms (``flow:*:read``, ``flow:read:extra``, ...) at the
# API boundary instead of letting them slip into ``authz_role.permissions``
# and silently fail the next policy sync.
_RESOURCE_TYPES = frozenset({"flow", "deployment", "project", "knowledge_base", "variable", "file", "share"})

# Union of every action enum value in ``services/authorization/actions.py``.
# A wildcard ``*`` is also accepted so a custom role can grant "all actions
# on this resource" without having to enumerate them. ``*`` on the resource
# side is intentionally NOT accepted: a role granting every action on every
# resource is effectively superuser and should not be expressible as a slug.
_ACTIONS = frozenset({"read", "write", "create", "delete", "execute", "deploy", "ingest", "update", "*"})

_PERMISSION_SLUG_RE = re.compile(r"^[a-z_]+:[a-z_*]+$")


def _validate_permission_slug(slug: str) -> str:
    # Pydantic coerces ``list[str]`` so we only ever see strings here; the
    # regex check carries the real format guarantee.
    if not _PERMISSION_SLUG_RE.fullmatch(slug):
        msg = (
            f"permission {slug!r} is not in the canonical "
            "'<resource>:<action>' form (e.g. 'flow:read', 'deployment:execute')"
        )
        raise ValueError(msg)
    resource, action = slug.split(":", 1)
    if resource not in _RESOURCE_TYPES:
        msg = f"permission {slug!r} has unknown resource {resource!r}; expected one of {sorted(_RESOURCE_TYPES)}"
        raise ValueError(msg)
    if action not in _ACTIONS:
        msg = f"permission {slug!r} has unknown action {action!r}; expected one of {sorted(_ACTIONS)}"
        raise ValueError(msg)
    return slug


class RoleCreate(BaseModel):
    """Payload for creating an authz_role row."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None)
    permissions: list[str] = Field(
        default_factory=list,
        description=(
            "Permission slugs in the canonical ``<resource>:<action>`` form — for "
            "example ``flow:read``, ``deployment:execute``, ``share:create``. "
            "Resources must be one of flow, deployment, project, knowledge_base, "
            "variable, file, share. Actions must be one of read, write, create, "
            "delete, execute, deploy, ingest, update, or ``*`` (all). A registered "
            "authorization plugin is responsible for compiling these into its "
            "policy format."
        ),
    )
    parent_role_id: UUID | None = Field(default=None)

    @field_validator("permissions")
    @classmethod
    def _validate_permissions(cls, value: list[str]) -> list[str]:
        return [_validate_permission_slug(s) for s in value]


class RoleUpdate(BaseModel):
    """Payload for updating an authz_role row (PATCH semantics — only set fields apply)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    permissions: list[str] | None = None
    parent_role_id: UUID | None = None

    @field_validator("permissions")
    @classmethod
    def _validate_permissions(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [_validate_permission_slug(s) for s in value]


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
