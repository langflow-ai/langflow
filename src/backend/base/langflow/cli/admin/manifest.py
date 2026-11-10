"""Stable declarative state contract for ``langflow admin``."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from langflow.services.authorization.permissions import validate_permission_slug

if TYPE_CHECKING:
    from pathlib import Path


class ManifestModel(BaseModel):
    """Strict base model so misspelled or unsafe fields fail validation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ManifestDocumentError(ValueError):
    """A parse error that never includes source text or secret values."""


class ManifestUser(ManifestModel):
    id: UUID | None = None
    username: str = Field(min_length=1)
    state: Literal["active", "disabled"] = "active"
    password_env: str | None = Field(default=None, min_length=1)


class ManifestTeam(ManifestModel):
    id: UUID | None = None
    adom_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str | None = None
    state: Literal["active", "disabled"] = "active"
    members: list[str] = Field(default_factory=list)


class ManifestRole(ManifestModel):
    id: UUID | None = None
    name: str = Field(min_length=1)
    description: str | None = None
    parent: str | None = None
    permissions: list[str] = Field(default_factory=list)

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, permissions: list[str]) -> list[str]:
        return [validate_permission_slug(slug) for slug in permissions]


class ManifestSubject(ManifestModel):
    type: Literal["user", "team"]
    name: str = Field(min_length=1)


class ManifestDomain(ManifestModel):
    type: Literal["global", "workspace", "project"] = "global"
    domain_id: UUID | None = None

    @model_validator(mode="after")
    def validate_domain_id(self) -> ManifestDomain:
        if self.type == "global" and self.domain_id is not None:
            msg = "domain_id must be omitted for a global assignment"
            raise ValueError(msg)
        if self.type != "global" and self.domain_id is None:
            msg = f"domain_id is required for a {self.type} assignment"
            raise ValueError(msg)
        return self


class ManifestAssignment(ManifestModel):
    subject: ManifestSubject
    role: str = Field(min_length=1)
    domain: ManifestDomain = Field(default_factory=ManifestDomain)


class AdminState(ManifestModel):
    """Top-level ``langflow.ai/v1`` administration manifest."""

    api_version: Literal["langflow.ai/v1"] = Field(alias="apiVersion")
    kind: Literal["AdminState"]
    users: list[ManifestUser] = Field(default_factory=list)
    teams: list[ManifestTeam] = Field(default_factory=list)
    roles: list[ManifestRole] = Field(default_factory=list)
    assignments: list[ManifestAssignment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_natural_keys(self) -> AdminState:
        _require_unique("user username", [item.username for item in self.users])
        _require_unique("team adom_name", [item.adom_name for item in self.teams])
        _require_unique("role name", [item.name for item in self.roles])
        _require_unique("user id", [item.id for item in self.users if item.id is not None])
        _require_unique("team id", [item.id for item in self.teams if item.id is not None])
        _require_unique("role id", [item.id for item in self.roles if item.id is not None])
        assignment_keys = [
            (
                item.subject.type,
                item.subject.name,
                item.role,
                item.domain.type,
                item.domain.domain_id,
            )
            for item in self.assignments
        ]
        _require_unique("assignment", assignment_keys)
        return self


class DirectoryConnectionTrust(ManifestModel):
    """Credential-free external OAuth trust metadata."""

    tenant_id: str = Field(min_length=1, max_length=64)
    issuer: str = Field(min_length=1, max_length=512)
    audience: str = Field(min_length=1, max_length=512)
    jwks_url: str = Field(min_length=1, max_length=2048)
    allowed_client_id: str = Field(min_length=1, max_length=256)


class DirectoryTeamLink(ManifestModel):
    group_id: UUID
    team_id: UUID
    origin: Literal["created", "linked"] = "linked"


class DirectoryRoleMapping(ManifestModel):
    group_id: UUID
    role_id: UUID
    domain: ManifestDomain = Field(default_factory=ManifestDomain)


class DirectoryState(ManifestModel):
    """Reviewed directory mapping intent; never contains SCIM catalog state."""

    api_version: Literal["langflow.ai/v1"] = Field(alias="apiVersion")
    kind: Literal["DirectoryState"]
    connection: DirectoryConnectionTrust | None = None
    team_links: list[DirectoryTeamLink] = Field(default_factory=list, alias="teamLinks")
    role_mappings: list[DirectoryRoleMapping] = Field(default_factory=list, alias="roleMappings")

    @model_validator(mode="after")
    def validate_mapping_keys(self) -> DirectoryState:
        _require_unique("directory group Team link", [item.group_id for item in self.team_links])
        _require_unique("directory-backed Team", [item.team_id for item in self.team_links])
        _require_unique(
            "directory role mapping",
            [(item.group_id, item.role_id, item.domain.type, item.domain.domain_id) for item in self.role_mappings],
        )
        return self


def _require_unique(label: str, values: list[object]) -> None:
    seen: set[object] = set()
    duplicates: set[object] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        msg = f"Duplicate {label} values: {sorted(map(str, duplicates))}"
        raise ValueError(msg)


def load_admin_state(path: Path) -> AdminState:
    """Load a YAML or JSON manifest using one strict model."""
    text = path.read_text(encoding="utf-8")
    try:
        raw = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON administration manifest at line {exc.lineno}, column {exc.colno}"
        raise ManifestDocumentError(msg) from exc
    except yaml.YAMLError as exc:
        msg = "Invalid YAML administration manifest"
        raise ManifestDocumentError(msg) from exc
    return AdminState.model_validate(raw)


def load_directory_state(path: Path) -> DirectoryState:
    """Load a strict credential-free directory mapping manifest."""
    text = path.read_text(encoding="utf-8")
    try:
        raw = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON directory manifest at line {exc.lineno}, column {exc.colno}"
        raise ManifestDocumentError(msg) from exc
    except yaml.YAMLError as exc:
        msg = "Invalid YAML directory manifest"
        raise ManifestDocumentError(msg) from exc
    return DirectoryState.model_validate(raw)


def dump_admin_state(state: AdminState, *, format_name: Annotated[Literal["yaml", "json"], Field()] = "yaml") -> str:
    """Serialize a manifest without introducing aliases or secret values."""
    data = state.model_dump(mode="json", by_alias=True, exclude_none=True)
    if format_name == "json":
        return json.dumps(data, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(data, sort_keys=False)


def dump_directory_state(
    state: DirectoryState,
    *,
    format_name: Annotated[Literal["yaml", "json"], Field()] = "yaml",
) -> str:
    """Serialize reviewed directory intent without catalog identities or secrets."""
    data = state.model_dump(mode="json", by_alias=True, exclude_none=True)
    if format_name == "json":
        return json.dumps(data, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(data, sort_keys=False)
