"""Pydantic schemas for /api/v1/authz/roles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from langflow.services.authorization.permissions import validate_permission_slug


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
# match — undermining the canonical-slug guarantee. The service-level
# permission validator is the authoritative source. ``*`` as a resource is
# never accepted; a role granting every action on every resource is effectively
# superuser and should not be expressible as a slug.
class RoleCreate(BaseModel):
    """Payload for creating an authz_role row."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None)
    permissions: list[str] = Field(
        default_factory=list,
        description=(
            "Permission slugs in the canonical ``<resource>:<action>`` form — for "
            "example ``flow:read``, ``deployment:execute``, ``share:create``. "
            "Resources must be one of user, team, role, flow, deployment, project, knowledge_base, "
            "variable, file, share, provider_account, voice, plus the narrow model-provider form "
            "``component:models/<provider-id>:read``. Actions are constrained per-resource (see "
            "``services/authorization/actions.py``): e.g. ``deploy`` is only valid "
            "on ``flow``, ``ingest`` only on ``knowledge_base``, ``update`` only on "
            "``share``. ``*`` is accepted only for resource vocabularies that expose it; "
            "administration resources use the explicit ``manage`` action. "
            "A registered authorization plugin is responsible for compiling these "
            "into its policy format."
        ),
    )
    parent_role_id: UUID | None = Field(default=None)

    @field_validator("permissions")
    @classmethod
    def _validate_permissions(cls, value: list[str]) -> list[str]:
        return [validate_permission_slug(slug) for slug in value]


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
        return [validate_permission_slug(slug) for slug in value]


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
