"""Validation for canonical authorization permission slugs."""

from __future__ import annotations

import re

from langflow.services.authorization.actions import (
    AdministrationAction,
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ProviderAccountAction,
    ShareAction,
    VariableAction,
    VoiceAction,
)

RESOURCE_ACTIONS: dict[str, frozenset[str]] = {
    "user": frozenset({action.value for action in AdministrationAction}),
    "team": frozenset({action.value for action in AdministrationAction}),
    "role": frozenset({action.value for action in AdministrationAction}),
    "flow": frozenset({action.value for action in FlowAction}) | {"*"},
    "deployment": frozenset({action.value for action in DeploymentAction}) | {"*"},
    "project": frozenset({action.value for action in ProjectAction}) | {"*"},
    "knowledge_base": frozenset({action.value for action in KnowledgeBaseAction}) | {"*"},
    "variable": frozenset({action.value for action in VariableAction}) | {"*"},
    "file": frozenset({action.value for action in FileAction}) | {"*"},
    "share": frozenset({action.value for action in ShareAction}) | {"*"},
    "provider_account": frozenset({action.value for action in ProviderAccountAction}) | {"*"},
    "voice": frozenset({action.value for action in VoiceAction}) | {"*"},
}

_PERMISSION_SLUG_RE = re.compile(r"^[a-z_]+:[a-z_*]+$")
_MODEL_COMPONENT_PERMISSION_RE = re.compile(r"^component:models/(?:[a-z0-9][a-z0-9._-]*|\*):read$")


def validate_permission_slug(slug: str) -> str:
    """Validate one permission against the resource-specific action vocabulary."""
    if _MODEL_COMPONENT_PERMISSION_RE.fullmatch(slug):
        return slug
    if not _PERMISSION_SLUG_RE.fullmatch(slug):
        msg = (
            f"permission {slug!r} is not in the canonical "
            "'<resource>:<action>' form (e.g. 'flow:read', 'deployment:execute')"
        )
        raise ValueError(msg)
    resource, action = slug.split(":", 1)
    allowed = RESOURCE_ACTIONS.get(resource)
    if allowed is None:
        msg = f"permission {slug!r} has unknown resource {resource!r}; expected one of {sorted(RESOURCE_ACTIONS)}"
        raise ValueError(msg)
    if action not in allowed:
        msg = (
            f"permission {slug!r} has unknown action {action!r} for resource {resource!r}; "
            f"expected one of {sorted(allowed)}"
        )
        raise ValueError(msg)
    return slug
