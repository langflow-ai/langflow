"""Validated permission ceilings for database-backed API keys."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ApiKeyScopeType = Literal["global", "workspace", "project"]
ResourceId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
_SCOPED_RESOURCES = frozenset({"flow", "deployment", "project"})
_ADMINISTRATION_RESOURCES = frozenset({"user", "team", "role"})


def api_key_resource_actions() -> dict[str, list[str]]:
    """Reuse the canonical action vocabulary without credential administration."""
    from langflow.services.authorization.permissions import RESOURCE_ACTIONS

    actions_by_resource = {
        **{
            name: sorted(actions - {"*"})
            for name, actions in RESOURCE_ACTIONS.items()
            if name not in _ADMINISTRATION_RESOURCES
        },
        "component": ["read"],
    }
    for resource in ("connection", "provider_account"):
        actions_by_resource[resource] = [
            action for action in actions_by_resource[resource] if action in {"read", "execute"}
        ]
    return actions_by_resource


def api_key_scope_types() -> dict[str, list[str]]:
    """Return only scopes represented by the existing resource model."""
    return {
        resource: ["global", "workspace", "project"] if resource in _SCOPED_RESOURCES else ["global"]
        for resource in api_key_resource_actions()
    }


class ApiKeyScope(BaseModel):
    """An existing RBAC domain boundary."""

    model_config = ConfigDict(extra="forbid")

    domain_type: ApiKeyScopeType = "global"  # pragma: allowlist secret
    domain_id: UUID | None = None

    @model_validator(mode="after")
    def validate_domain(self) -> ApiKeyScope:
        if self.domain_type == "global" and self.domain_id is not None:
            msg = "Global scope cannot specify domain_id"
            raise ValueError(msg)
        if self.domain_type != "global" and self.domain_id is None:
            msg = "Workspace and project scopes require domain_id"
            raise ValueError(msg)
        return self


class ApiKeyRoleGrant(ApiKeyScope):
    """A live role definition used as a permission ceiling."""

    role_id: UUID


class ApiKeyResourceRestriction(ApiKeyScope):
    """One allowlist entry intersected with owner access and selected roles."""

    resource_type: str
    actions: list[str] = Field(min_length=1, max_length=32)
    resource_ids: list[ResourceId] | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_resource_actions(self) -> ApiKeyResourceRestriction:
        allowed = api_key_resource_actions().get(self.resource_type)
        if allowed is None or any(action not in allowed for action in self.actions):
            msg = "Unsupported API key resource or action"
            raise ValueError(msg)
        if self.domain_type not in api_key_scope_types()[self.resource_type]:
            msg = "This resource does not support workspace or project scope"
            raise ValueError(msg)
        if len(set(self.actions)) != len(self.actions):
            msg = "Actions must be unique"
            raise ValueError(msg)
        if self.resource_ids is not None and (
            len(set(self.resource_ids)) != len(self.resource_ids) or any("*" in value for value in self.resource_ids)
        ):
            msg = "Resource IDs must be unique exact identifiers"
            raise ValueError(msg)
        return self


class ApiKeyPermissionPolicy(BaseModel):
    """Non-empty key limits that never replace the owner's current access."""

    model_config = ConfigDict(extra="forbid")

    roles: list[ApiKeyRoleGrant] = Field(default_factory=list, max_length=100)
    restrictions: list[ApiKeyResourceRestriction] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_nonempty(self) -> ApiKeyPermissionPolicy:
        if not self.roles and not self.restrictions:
            msg = "Restricted keys require roles or explicit restrictions"
            raise ValueError(msg)
        return self


def validate_permission_policy(value: Any) -> dict[str, Any] | None:
    """Keep persisted and returned policies as JSON-compatible dictionaries."""
    if value is None:
        return None
    return ApiKeyPermissionPolicy.model_validate(value).model_dump(mode="json", exclude_unset=True)


class ApiKeyPermissionsUpdate(BaseModel):
    """Replace a key's complete permission policy, or explicitly remove it."""

    model_config = ConfigDict(extra="forbid")

    permissions: ApiKeyPermissionPolicy | None


class ApiKeyPermissionRoleOption(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class ApiKeyPermissionOptions(BaseModel):
    supported: bool = False
    roles: list[ApiKeyPermissionRoleOption] = Field(default_factory=list)
    resource_actions: dict[str, list[str]] = Field(default_factory=dict)
    scope_types: dict[str, list[str]] = Field(default_factory=dict)
