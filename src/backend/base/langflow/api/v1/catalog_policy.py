"""Superuser administration API for global catalog block policy."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from lfx.services.catalog_policy import BaseCatalogPolicyService, CatalogPolicySnapshot

from langflow.api.v1.policy_bundle_errors import policy_bundle_revision_conflict
from langflow.api.v1.schemas.catalog_policy import CatalogPolicyBlockedSet, CatalogPolicyRead
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization.audit import audit_decision
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_catalog_policy_service
from langflow.services.policy_bundle import PolicyBundleRevisionConflictError

router = APIRouter(prefix="/catalog-policy", tags=["Catalog Policy"])


def _active_snapshot(service: BaseCatalogPolicyService) -> tuple[CatalogPolicySnapshot, bool]:
    external_snapshot = service.external_policy_snapshot
    if external_snapshot is not None:
        return external_snapshot, True
    return service.snapshot, False


def _response(blocked: frozenset[str], *, managed_externally: bool) -> CatalogPolicyRead:
    return CatalogPolicyRead(
        blocked=sorted(blocked),
        managed_externally=managed_externally,
    )


def _raise_if_externally_managed(service: BaseCatalogPolicyService) -> None:
    if service.external_policy_snapshot is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Catalog policy is externally managed and cannot be changed through this API.",
        )
    if not service.supports_policy_bundle_updates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Configured catalog policy service does not support shared policy bundle updates; "
                "upgrade the plugin before changing database-backed policy"
            ),
        )


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


@router.get("/components", response_model=CatalogPolicyRead)
async def get_component_policy(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyRead:
    """Return the complete global component block set."""
    service = get_catalog_policy_service()
    snapshot, managed_externally = _active_snapshot(service)
    return _response(snapshot.blocked_component_keys, managed_externally=managed_externally)


@router.put("/components", response_model=CatalogPolicyRead)
async def replace_component_policy(
    payload: CatalogPolicyBlockedSet,
    admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyRead:
    """Replace the complete global component block set."""
    service = get_catalog_policy_service()
    _raise_if_externally_managed(service)
    try:
        update = await service.replace_blocked_component_keys(
            payload.blocked,
            actor_user_id=admin.id,
        )
    except PolicyBundleRevisionConflictError as exc:
        raise policy_bundle_revision_conflict(exc) from exc
    await _audit_update(
        user_id=admin.id,
        resource_kind="component",
        added=update.added,
        removed=update.removed,
    )
    return _response(update.snapshot.blocked_component_keys, managed_externally=False)


@router.get("/templates", response_model=CatalogPolicyRead)
async def get_template_policy(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyRead:
    """Return the complete global template block set."""
    service = get_catalog_policy_service()
    snapshot, managed_externally = _active_snapshot(service)
    return _response(snapshot.blocked_template_keys, managed_externally=managed_externally)


@router.put("/templates", response_model=CatalogPolicyRead)
async def replace_template_policy(
    payload: CatalogPolicyBlockedSet,
    admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyRead:
    """Replace the complete global template block set."""
    service = get_catalog_policy_service()
    _raise_if_externally_managed(service)
    try:
        update = await service.replace_blocked_template_keys(
            payload.blocked,
            actor_user_id=admin.id,
        )
    except PolicyBundleRevisionConflictError as exc:
        raise policy_bundle_revision_conflict(exc) from exc
    await _audit_update(
        user_id=admin.id,
        resource_kind="template",
        added=update.added,
        removed=update.removed,
    )
    return _response(update.snapshot.blocked_template_keys, managed_externally=False)


__all__ = ["router"]
