"""Per-user effective-permissions endpoint, used by the frontend permission gate.

The UI calls this once per page load with the list of resource IDs it wants to
render and learns which actions to enable/disable per resource — without making
a 403-triggering request for each one. Backed by
:meth:`BaseAuthorizationService.get_effective_permissions`; OSS pass-through
returns every action for every ID (no policy applied) and a registered
authorization plugin overrides it with a tighter implementation.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

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

# Default action vocabulary aligned with the authorization plugin's known actions.
_DEFAULT_ACTIONS: tuple[str, ...] = ("read", "write", "execute", "delete", "create")
_MAX_RESOURCE_IDS = 500
# Cap actions per request to bound the batch_enforce cartesian product
# (resource_ids x actions). Headroom over the 6 known actions
# (read/write/execute/delete/create/manage) covers future additions without
# letting a client request `["read"] * 100000` to flood the enforcer.
_MAX_ACTIONS = 10


class EffectivePermissionsRequest(BaseModel):
    """Body for :func:`get_effective_permissions`."""

    resource_type: ResourceTypeLiteral
    resource_ids: list[UUID] = Field(
        ...,
        description="Resource IDs to evaluate. Capped at 500 per request to keep batch_enforce bounded.",
    )
    actions: list[str] | None = Field(
        default=None,
        description=(
            "Actions to check. Each entry is lowercased and de-duplicated; the list is "
            f"capped at {_MAX_ACTIONS}. Defaults to read/write/execute/delete/create."
        ),
    )
    domain: str = Field(
        default="*",
        description="Authorization domain — typically ``project:{folder_id}`` or ``*``.",
    )

    @field_validator("actions")
    @classmethod
    def _normalize_actions(cls, value: list[str] | None) -> list[str] | None:
        """Lowercase, strip, de-duplicate (order-preserving), and cap the actions list.

        Returns ``None`` when the caller omitted the field (handler substitutes
        ``_DEFAULT_ACTIONS``). An empty list after normalization also returns
        ``None`` so the default kicks in rather than producing an empty cartesian
        product downstream.
        """
        if value is None:
            return None
        seen: set[str] = set()
        normalized: list[str] = []
        for raw in value:
            if not isinstance(raw, str):
                # Pydantic field_validators must raise ValueError (not TypeError)
                # to be wrapped into a ValidationError -> HTTP 422 response.
                msg = "actions must be strings"
                raise ValueError(msg)  # noqa: TRY004
            cleaned = raw.strip().lower()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            normalized.append(cleaned)
        if len(normalized) > _MAX_ACTIONS:
            msg = f"actions capped at {_MAX_ACTIONS} unique entries"
            raise ValueError(msg)
        return normalized or None


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
