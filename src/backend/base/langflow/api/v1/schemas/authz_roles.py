"""Pydantic schemas for /api/v1/authz/roles."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ShareAction,
    VariableAction,
)

# Canonical permission slug is ``<resource>:<action>`` — matches the
# system-role seed in ``8d3a1f9c2e0b_seed_authz_system_roles`` and the
# ``"{resource}:{action}"`` contract documented in AGENTS.md. Plugins
# that compile these to policy rows expect this exact shape, so we
# reject other forms (``flow:*:read``, ``flow:read:extra``, ...) at the
# API boundary instead of letting them slip into ``authz_role.permissions``
# and silently fail the next policy sync.
#
# Resource and action validation is *coupled*: each resource only supports
# the actions exposed by its enum in ``services/authorization/actions.py``.
# Validating them independently would let admins create permissions like
# ``file:deploy`` or ``share:execute`` that no enforce() call could ever
# match — undermining the canonical-slug guarantee. The map below is the
# authoritative source. ``*`` (all actions on that resource) is always
# accepted; ``*`` as a resource is NOT — a role granting every action on
# every resource is effectively superuser and should not be expressible
# as a slug.
_RESOURCE_ACTIONS: dict[str, frozenset[str]] = {
    "flow": frozenset({a.value for a in FlowAction}) | {"*"},
    "deployment": frozenset({a.value for a in DeploymentAction}) | {"*"},
    "project": frozenset({a.value for a in ProjectAction}) | {"*"},
    "knowledge_base": frozenset({a.value for a in KnowledgeBaseAction}) | {"*"},
    "variable": frozenset({a.value for a in VariableAction}) | {"*"},
    "file": frozenset({a.value for a in FileAction}) | {"*"},
    "share": frozenset({a.value for a in ShareAction}) | {"*"},
}

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
    allowed = _RESOURCE_ACTIONS.get(resource)
    if allowed is None:
        msg = f"permission {slug!r} has unknown resource {resource!r}; expected one of {sorted(_RESOURCE_ACTIONS)}"
        raise ValueError(msg)
    if action not in allowed:
        # Surface the resource-specific action vocabulary so callers can
        # fix the slug without consulting the enums directly.
        msg = (
            f"permission {slug!r} has unknown action {action!r} for resource {resource!r}; "
            f"expected one of {sorted(allowed)}"
        )
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
            "variable, file, share. Actions are constrained per-resource (see "
            "``services/authorization/actions.py``): e.g. ``deploy`` is only valid "
            "on ``flow``, ``ingest`` only on ``knowledge_base``, ``update`` only on "
            "``share``. ``*`` (all actions on that resource) is always accepted. "
            "A registered authorization plugin is responsible for compiling these "
            "into its policy format."
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
