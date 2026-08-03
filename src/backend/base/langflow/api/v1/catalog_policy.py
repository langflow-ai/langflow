"""Superuser administration API for global catalog block policy."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends

from langflow.api.v1.schemas.catalog_policy import CatalogPolicyBlockedSet
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization.audit import audit_decision
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_catalog_policy_service

router = APIRouter(prefix="/catalog-policy", tags=["Catalog Policy"])


def _response(blocked: frozenset[str]) -> CatalogPolicyBlockedSet:
    return CatalogPolicyBlockedSet(blocked=sorted(blocked))


async def _audit_update(
    *,
    user_id: UUID,
    resource_kind: Literal["component", "template"],
    added: frozenset[str],
    removed: frozenset[str],
) -> None:
    """Emit one post-commit audit event per changed catalog key."""
    for key in sorted(added):
        await audit_decision(
            user_id=user_id,
            action="catalog:block",
            obj=f"{resource_kind}:{key}",
            result="allow",
            details={
                "resource_kind": resource_kind,
                "resource_key": key,
            },
        )
    for key in sorted(removed):
        await audit_decision(
            user_id=user_id,
            action="catalog:unblock",
            obj=f"{resource_kind}:{key}",
            result="allow",
            details={
                "resource_kind": resource_kind,
                "resource_key": key,
            },
        )


@router.get("/components", response_model=CatalogPolicyBlockedSet)
async def get_component_policy(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyBlockedSet:
    """Return the complete global component block set."""
    service = get_catalog_policy_service()
    return _response(service.snapshot.blocked_component_keys)


@router.put("/components", response_model=CatalogPolicyBlockedSet)
async def replace_component_policy(
    payload: CatalogPolicyBlockedSet,
    admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyBlockedSet:
    """Replace the complete global component block set."""
    service = get_catalog_policy_service()
    update = await service.replace_blocked_component_keys(
        payload.blocked,
        actor_user_id=admin.id,
    )
    await _audit_update(
        user_id=admin.id,
        resource_kind="component",
        added=update.added,
        removed=update.removed,
    )
    return _response(update.snapshot.blocked_component_keys)


@router.get("/templates", response_model=CatalogPolicyBlockedSet)
async def get_template_policy(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyBlockedSet:
    """Return the complete global template block set."""
    service = get_catalog_policy_service()
    return _response(service.snapshot.blocked_template_keys)


@router.put("/templates", response_model=CatalogPolicyBlockedSet)
async def replace_template_policy(
    payload: CatalogPolicyBlockedSet,
    admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyBlockedSet:
    """Replace the complete global template block set."""
    service = get_catalog_policy_service()
    update = await service.replace_blocked_template_keys(
        payload.blocked,
        actor_user_id=admin.id,
    )
    await _audit_update(
        user_id=admin.id,
        resource_kind="template",
        added=update.added,
        removed=update.removed,
    )
    return _response(update.snapshot.blocked_template_keys)


__all__ = ["router"]
