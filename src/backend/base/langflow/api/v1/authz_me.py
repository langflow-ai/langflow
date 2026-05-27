"""Per-user effective-permissions endpoint, used by the frontend permission gate.

The UI calls this once per page load with the list of resource IDs it wants to
render and learns which actions to enable/disable per resource — without making
a 403-triggering request for each one. Backed by
:meth:`BaseAuthorizationService.get_effective_permissions`; OSS pass-through
returns every action for every ID (no policy applied) and the Casbin plugin
overrides it with a tighter implementation.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/me", tags=["Authorization"])

# Match the resource slugs used by ensure_*_permission helpers.
ResourceTypeLiteral = Literal[
    "flow",
    "deployment",
    "project",
    "knowledge_base",
    "variable",
    "file",
    "component",
]

# Default action vocabulary — matches Casbin's KNOWN_ACTIONS in EE roles.py.
_DEFAULT_ACTIONS: tuple[str, ...] = ("read", "write", "execute", "delete", "create")
_MAX_RESOURCE_IDS = 500


class EffectivePermissionsRequest(BaseModel):
    """Body for :func:`get_effective_permissions`."""

    resource_type: ResourceTypeLiteral
    resource_ids: list[UUID] = Field(
        ...,
        description="Resource IDs to evaluate. Capped at 500 per request to keep batch_enforce bounded.",
    )
    actions: list[str] | None = Field(
        default=None,
        description="Actions to check. Defaults to read/write/execute/delete/create.",
    )
    domain: str = Field(
        default="*",
        description="Casbin domain — typically ``project:{folder_id}`` or ``*``.",
    )


class EffectivePermissionsResponse(BaseModel):
    """Response: ``{resource_id: [allowed_actions]}``."""

    resource_type: ResourceTypeLiteral
    permissions: dict[UUID, list[str]]


@router.post("/permissions", response_model=EffectivePermissionsResponse)
async def get_effective_permissions(
    body: EffectivePermissionsRequest,
    current_user: CurrentActiveUser,
) -> EffectivePermissionsResponse:
    """Return per-resource allowed actions for the current user.

    Use this to render the UI permission gate (greyed-out buttons etc.) without
    flooding the audit log with denied probes. Empty list for a resource_id
    means the user cannot perform any of the requested actions on that resource.
    """
    if not body.resource_ids:
        return EffectivePermissionsResponse(resource_type=body.resource_type, permissions={})
    if len(body.resource_ids) > _MAX_RESOURCE_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"resource_ids capped at {_MAX_RESOURCE_IDS}",
        )

    authz = get_authorization_service()
    actions = tuple(body.actions) if body.actions else _DEFAULT_ACTIONS
    permissions = await authz.get_effective_permissions(
        user_id=current_user.id,
        resource_type=body.resource_type,
        resource_ids=body.resource_ids,
        actions=actions,
        domain=body.domain,
        context={"is_superuser": getattr(current_user, "is_superuser", False)},
    )
    return EffectivePermissionsResponse(
        resource_type=body.resource_type,
        permissions=permissions,
    )
