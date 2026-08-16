"""Superuser administration API for global catalog block policy."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Annotated, Literal, NamedTuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from lfx.services.catalog_policy import BaseCatalogPolicyService, CatalogPolicySnapshot
from lfx.services.deps import session_scope_readonly
from lfx.utils.component_aliases import build_component_identity_index
from lfx.utils.flow_validation import collect_catalog_component_keys
from sqlmodel import col, select

from langflow.api.v1.policy_bundle_errors import policy_bundle_revision_conflict
from langflow.api.v1.schemas.catalog_policy import (
    CATALOG_POLICY_KEY_MAX_LENGTH,
    CatalogPolicyBlockedSet,
    CatalogPolicyRead,
    CatalogPolicyUsageFlowRef,
    CatalogPolicyUsageFlowsRead,
    CatalogPolicyUsageRead,
)
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization.audit import audit_decision
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_catalog_policy_service
from langflow.services.policy_bundle import PolicyBundleRevisionConflictError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lfx.utils.component_aliases import ComponentIdentityIndex

router = APIRouter(prefix="/catalog-policy", tags=["Catalog Policy"])

USAGE_FLOWS_DEFAULT_LIMIT = 100
USAGE_FLOWS_MAX_LIMIT = 500
# How long one flow-table scan is reused by the usage endpoints. Governance
# counts may lag flow writes by up to this window; policy writes never change
# usage data, so a refetch after saving a policy is served from cache exactly.
USAGE_SCAN_CACHE_TTL_SECONDS = 30.0


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


class _FlowUsage(NamedTuple):
    """One flow's identity, display name, and exact stored component keys."""

    flow_id: UUID
    name: str
    component_keys: frozenset[str]


async def _load_flow_component_usage() -> tuple[list[_FlowUsage], int]:
    """Return per-flow component keys and the total number of flows scanned.

    Saved components (``is_component``) are excluded — they are palette
    entries, not flows. Every remaining flow's stored graph is scanned,
    including nested flows inlined in legacy Run Flow nodes. This reads each
    flow's full ``data`` payload, so it is reserved for the superuser
    governance endpoints below rather than any per-request path.
    """
    async with session_scope_readonly() as session:
        rows = (
            await session.exec(
                select(Flow.id, Flow.name, Flow.data).where(
                    col(Flow.is_component).is_not(True),
                    col(Flow.data).is_not(None),
                )
            )
        ).all()
    usage = [
        _FlowUsage(flow_id=flow_id, name=name, component_keys=component_keys)
        for flow_id, name, data in rows
        if (component_keys := collect_catalog_component_keys(data))
    ]
    return usage, len(rows)


class _UsageScan(NamedTuple):
    """An immutable flow-table scan plus the monotonic instant it was taken."""

    usage: tuple[_FlowUsage, ...]
    flows_scanned: int
    loaded_at: float


_usage_scan_cache: _UsageScan | None = None


async def _cached_flow_component_usage() -> tuple[Sequence[_FlowUsage], int]:
    """Serve the flow scan from a short process-local cache.

    Both usage endpoints share one scan per TTL window, so an admin page that
    fetches counts on mount and refetches after every policy save costs one
    flow-table read per window instead of one per request. There is
    deliberately no lock: concurrent cache misses each scan and the last
    writer wins, which only duplicates work an uncached implementation would
    do anyway. The cache is per-process; workers converge within one TTL.
    """
    global _usage_scan_cache  # noqa: PLW0603 - module-level TTL cache
    cached = _usage_scan_cache
    if cached is not None and time.monotonic() - cached.loaded_at < USAGE_SCAN_CACHE_TTL_SECONDS:
        return cached.usage, cached.flows_scanned
    usage, flows_scanned = await _load_flow_component_usage()
    _usage_scan_cache = _UsageScan(
        usage=tuple(usage),
        flows_scanned=flows_scanned,
        loaded_at=time.monotonic(),
    )
    return usage, flows_scanned


async def _usage_identity_index() -> ComponentIdentityIndex:
    """Return the collision-aware identity index for the current registry.

    Built from the same registry mapping the palette endpoint filters, so
    usage numbers match what catalog enforcement would actually block.
    """
    from langflow.interface.components import get_and_cache_all_types_dict, get_component_identity_index
    from langflow.services.deps import get_settings_service

    all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())
    index = get_component_identity_index(all_types)
    if index is None:
        # Only a None mapping can yield None; keep the type checker satisfied.
        index = build_component_identity_index(all_types)
    return index


@router.get("/usage", response_model=CatalogPolicyUsageRead)
async def get_component_usage(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
) -> CatalogPolicyUsageRead:
    """Return how many flows use each component.

    Counts are keyed by canonical registry identity — a flow node saved under
    a legacy alias is counted under the component it resolves to today, the
    same resolution catalog enforcement applies. Keys not present in the
    registry (custom or synthetic components) are counted under their exact
    stored key. Each flow is counted at most once per component. Counts may
    lag flow writes by up to ``USAGE_SCAN_CACHE_TTL_SECONDS``.
    """
    usage, flows_scanned = await _cached_flow_component_usage()
    identity_index = await _usage_identity_index()

    counts: dict[str, int] = {}
    for flow in usage:
        for identity in identity_index.resolve_many(flow.component_keys):
            counts[identity] = counts.get(identity, 0) + 1
    return CatalogPolicyUsageRead(
        components=dict(sorted(counts.items())),
        flows_scanned=flows_scanned,
    )


@router.get("/usage/flows", response_model=CatalogPolicyUsageFlowsRead)
async def get_component_usage_flows(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    component: Annotated[
        str,
        Query(
            min_length=1,
            max_length=CATALOG_POLICY_KEY_MAX_LENGTH,
            description="Component key to look up; aliases resolve like catalog enforcement.",
        ),
    ],
    limit: Annotated[int, Query(ge=1, le=USAGE_FLOWS_MAX_LIMIT)] = USAGE_FLOWS_DEFAULT_LIMIT,
) -> CatalogPolicyUsageFlowsRead:
    """Return the flows that would be affected by blocking one component key.

    A flow matches when the queried key and any of the flow's stored keys
    resolve to a shared canonical identity — the same matching rule flow
    writes and runs enforce. Flows are sorted by name, then id, and truncated
    to ``limit``; ``total`` always reports the full match count. Results may
    lag flow writes by up to ``USAGE_SCAN_CACHE_TTL_SECONDS``.
    """
    component = component.strip()
    if not component:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="component must not be blank",
        )
    usage, _flows_scanned = await _cached_flow_component_usage()
    identity_index = await _usage_identity_index()

    target_identities = identity_index.resolve(component)
    matches = [
        flow for flow in usage if not target_identities.isdisjoint(identity_index.resolve_many(flow.component_keys))
    ]
    matches.sort(key=lambda flow: (flow.name.casefold(), str(flow.flow_id)))
    return CatalogPolicyUsageFlowsRead(
        component=component,
        total=len(matches),
        flows=[CatalogPolicyUsageFlowRef(id=flow.flow_id, name=flow.name) for flow in matches[:limit]],
    )


__all__ = ["router"]
