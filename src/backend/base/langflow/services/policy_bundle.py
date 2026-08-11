"""Atomic persistence and runtime publication for deployment policy bundles."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from lfx.base.models.provider_registry import resolve_provider_id
from lfx.services.model_provider_policy import ModelProviderPolicyService, normalize_blocked_model_key
from lfx.services.policy_bundle import PolicyBundleSnapshot, policy_bundle_content_hash
from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.database.models.catalog_policy import (
    CatalogPolicyMode,
    CatalogPolicyRule,
    CatalogPolicyScope,
    CatalogResourceKind,
)
from langflow.services.database.models.model_provider_policy import (
    MODEL_PROVIDER_POLICY_SINGLETON_ID,
    ModelProviderPolicy,
)
from langflow.services.database.models.policy_bundle import (
    POLICY_BUNDLE_REASON_MAX_LENGTH,
    POLICY_BUNDLE_SINGLETON_ID,
    POLICY_BUNDLE_SOURCE_MAX_LENGTH,
    PolicyBundleActive,
    PolicyBundleRevision,
)

if TYPE_CHECKING:
    from collections.abc import Collection
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

_STABLE_PROVIDER_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,254}", flags=re.ASCII)
_POLICY_SOURCE_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}", flags=re.ASCII)


class PolicyBundleNotInitializedError(RuntimeError):
    """The active bundle singleton or its immutable revision is unavailable."""


class PolicyBundleRevisionConflictError(RuntimeError):
    """A writer used a stale expected revision."""

    def __init__(self, *, expected_revision: int, active_revision: int) -> None:
        self.expected_revision = expected_revision
        self.active_revision = active_revision
        super().__init__(
            f"Policy bundle revision conflict: expected {expected_revision}, active revision is {active_revision}"
        )


class PolicyBundleApplicationNotSupportedError(RuntimeError):
    """Raised when a database-owned catalog plugin cannot apply shared bundles."""


def ensure_policy_bundle_application_supported() -> None:
    """Reject writes that the active database-owned catalog plugin cannot enforce."""
    from lfx.services.deps import get_catalog_policy_service

    catalog_service = get_catalog_policy_service()
    if catalog_service.external_policy_snapshot is None and not catalog_service.supports_policy_bundle_updates:
        msg = (
            "Configured catalog policy service does not support shared policy bundle updates; "
            "upgrade the plugin before changing database-backed policy"
        )
        raise PolicyBundleApplicationNotSupportedError(msg)


def _normalize_provider_ids(provider_ids: Collection[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for provider_id in provider_ids:
        canonical = resolve_provider_id(provider_id.strip())
        if _STABLE_PROVIDER_ID_RE.fullmatch(canonical) is None:
            msg = "Model provider IDs must use stable lowercase identifier syntax"
            raise ValueError(msg)
        normalized.add(canonical)
    return frozenset(normalized)


def _normalize_catalog_keys(keys: Collection[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for raw_key in keys:
        key = raw_key.strip()
        if not key:
            msg = "Catalog policy keys must not be empty"
            raise ValueError(msg)
        normalized.add(key)
    return frozenset(normalized)


def _normalize_model_keys(keys: Collection[str]) -> frozenset[str]:
    return frozenset(normalize_blocked_model_key(raw_key) for raw_key in keys)


def _normalize_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    normalized = reason.strip()
    if not normalized:
        return None
    if len(normalized) > POLICY_BUNDLE_REASON_MAX_LENGTH:
        msg = f"Policy bundle reason must not exceed {POLICY_BUNDLE_REASON_MAX_LENGTH} characters"
        raise ValueError(msg)
    return normalized


def _normalize_source(source: str) -> str:
    normalized = source.strip().lower()
    if len(normalized) > POLICY_BUNDLE_SOURCE_MAX_LENGTH or _POLICY_SOURCE_RE.fullmatch(normalized) is None:
        msg = "Policy bundle source must use lowercase identifier syntax"
        raise ValueError(msg)
    return normalized


def _snapshot_from_row(row: PolicyBundleRevision, *, initialized: bool | None = None) -> PolicyBundleSnapshot:
    return PolicyBundleSnapshot(
        revision=row.revision,
        initialized=row.initialized if initialized is None else initialized,
        source=row.source,
        approved_provider_ids=frozenset(row.approved_provider_ids),
        blocked_component_keys=frozenset(row.blocked_component_keys),
        blocked_template_keys=frozenset(row.blocked_template_keys),
        blocked_model_keys=frozenset(row.blocked_model_keys or []),
        content_hash=row.content_hash,
        created_at=row.created_at,
        created_by=row.created_by,
        reason=row.reason,
        rollback_of_revision=row.rollback_of_revision,
    )


async def get_policy_bundle_state(
    session: AsyncSession,
    *,
    revision: int | None = None,
) -> PolicyBundleSnapshot:
    """Read the active or requested immutable bundle revision."""
    target_revision = revision
    initialized: bool | None = None
    if target_revision is None:
        active = await session.get(
            PolicyBundleActive,
            POLICY_BUNDLE_SINGLETON_ID,
            populate_existing=True,
        )
        if active is None:
            msg = "Active policy bundle is missing; apply the latest database migrations"
            raise PolicyBundleNotInitializedError(msg)
        target_revision = active.revision
        initialized = active.initialized

    statement = (
        select(PolicyBundleRevision)
        .where(PolicyBundleRevision.revision == target_revision)
        .execution_options(populate_existing=True)
    )
    row = (await session.exec(statement)).one_or_none()
    if row is None:
        msg = f"Policy bundle revision {target_revision} is missing"
        raise PolicyBundleNotInitializedError(msg)
    return _snapshot_from_row(row, initialized=initialized)


async def list_policy_bundle_history(
    session: AsyncSession,
    *,
    limit: int = 50,
    before_revision: int | None = None,
) -> list[PolicyBundleSnapshot]:
    """Return newest-first immutable bundle history."""
    statement = select(PolicyBundleRevision)
    if before_revision is not None:
        statement = statement.where(PolicyBundleRevision.revision < before_revision)
    statement = statement.order_by(col(PolicyBundleRevision.revision).desc()).limit(limit)
    return [_snapshot_from_row(row) for row in (await session.exec(statement)).all()]


async def _active_revision(session: AsyncSession) -> int:
    active = await session.get(
        PolicyBundleActive,
        POLICY_BUNDLE_SINGLETON_ID,
        populate_existing=True,
    )
    if active is None:
        msg = "Active policy bundle is missing; apply the latest database migrations"
        raise PolicyBundleNotInitializedError(msg)
    return active.revision


async def _sync_legacy_policy(
    session: AsyncSession,
    snapshot: PolicyBundleSnapshot,
    *,
    actor_user_id: UUID | None,
) -> None:
    """Dual-write the N-1 stores without deleting reserved catalog rules."""
    provider_table = ModelProviderPolicy.__table__
    result = await session.exec(
        update(provider_table)
        .where(provider_table.c.id == MODEL_PROVIDER_POLICY_SINGLETON_ID)
        .values(
            approved_provider_ids=sorted(snapshot.approved_provider_ids),
            version=snapshot.revision,
        )
    )
    if result.rowcount != 1:
        msg = "Model-provider policy singleton is missing; apply the latest database migrations"
        raise PolicyBundleNotInitializedError(msg)

    statement = select(CatalogPolicyRule).where(
        CatalogPolicyRule.mode == CatalogPolicyMode.BLOCK.value,
        CatalogPolicyRule.scope == CatalogPolicyScope.GLOBAL.value,
        col(CatalogPolicyRule.domain_id).is_(None),
        CatalogPolicyRule.resource_kind.in_((CatalogResourceKind.COMPONENT.value, CatalogResourceKind.TEMPLATE.value)),
    )
    rows = list((await session.exec(statement)).all())
    rows_by_kind = {
        CatalogResourceKind.COMPONENT: {
            row.resource_key: row for row in rows if row.resource_kind == CatalogResourceKind.COMPONENT.value
        },
        CatalogResourceKind.TEMPLATE: {
            row.resource_key: row for row in rows if row.resource_kind == CatalogResourceKind.TEMPLATE.value
        },
    }
    desired_by_kind = {
        CatalogResourceKind.COMPONENT: snapshot.blocked_component_keys,
        CatalogResourceKind.TEMPLATE: snapshot.blocked_template_keys,
    }
    for resource_kind, current_rows in rows_by_kind.items():
        desired = desired_by_kind[resource_kind]
        for key in set(current_rows) - desired:
            await session.delete(current_rows[key])
        for key in desired - set(current_rows):
            session.add(
                CatalogPolicyRule(
                    resource_kind=resource_kind.value,
                    resource_key=key,
                    mode=CatalogPolicyMode.BLOCK.value,
                    scope=CatalogPolicyScope.GLOBAL.value,
                    domain_id=None,
                    created_by=actor_user_id,
                )
            )


async def replace_policy_bundle_state(
    session: AsyncSession,
    *,
    expected_revision: int,
    approved_provider_ids: Collection[str],
    blocked_component_keys: Collection[str],
    blocked_template_keys: Collection[str],
    blocked_model_keys: Collection[str] = (),
    actor_user_id: UUID | None,
    reason: str | None = None,
    rollback_of_revision: int | None = None,
    source: str = "api",
    require_uninitialized: bool = False,
) -> PolicyBundleSnapshot:
    """Create and activate one complete immutable revision in one transaction."""
    providers = _normalize_provider_ids(approved_provider_ids)
    components = _normalize_catalog_keys(blocked_component_keys)
    templates = _normalize_catalog_keys(blocked_template_keys)
    models = _normalize_model_keys(blocked_model_keys)
    normalized_reason = _normalize_reason(reason)
    normalized_source = _normalize_source(source)
    new_revision = expected_revision + 1

    active_table = PolicyBundleActive.__table__
    conditions = [
        active_table.c.id == POLICY_BUNDLE_SINGLETON_ID,
        active_table.c.revision == expected_revision,
    ]
    if require_uninitialized:
        conditions.append(active_table.c.initialized.is_(False))
    result = await session.exec(
        update(active_table)
        .where(
            *conditions,
        )
        .values(revision=new_revision, initialized=True, updated_at=sa.func.now())
    )
    if result.rowcount != 1:
        active_revision = await _active_revision(session)
        await session.rollback()
        raise PolicyBundleRevisionConflictError(
            expected_revision=expected_revision,
            active_revision=active_revision,
        )

    created_at = datetime.now(timezone.utc)
    snapshot = PolicyBundleSnapshot(
        revision=new_revision,
        initialized=True,
        source=normalized_source,
        approved_provider_ids=providers,
        blocked_component_keys=components,
        blocked_template_keys=templates,
        blocked_model_keys=models,
        content_hash=policy_bundle_content_hash(
            approved_provider_ids=providers,
            blocked_component_keys=components,
            blocked_template_keys=templates,
            blocked_model_keys=models,
        ),
        created_at=created_at,
        created_by=actor_user_id,
        reason=normalized_reason,
        rollback_of_revision=rollback_of_revision,
    )
    session.add(
        PolicyBundleRevision(
            revision=snapshot.revision,
            initialized=snapshot.initialized,
            approved_provider_ids=sorted(snapshot.approved_provider_ids),
            blocked_component_keys=sorted(snapshot.blocked_component_keys),
            blocked_template_keys=sorted(snapshot.blocked_template_keys),
            blocked_model_keys=sorted(snapshot.blocked_model_keys),
            content_hash=snapshot.content_hash,
            source=normalized_source,
            created_at=created_at,
            created_by=actor_user_id,
            reason=normalized_reason,
            rollback_of_revision=rollback_of_revision,
        )
    )
    await _sync_legacy_policy(session, snapshot, actor_user_id=actor_user_id)
    await session.commit()
    return snapshot


async def rollback_policy_bundle_state(
    session: AsyncSession,
    *,
    expected_revision: int,
    target_revision: int,
    actor_user_id: UUID | None,
    reason: str | None = None,
) -> PolicyBundleSnapshot:
    """Reactivate old content as a new monotonically increasing revision."""
    target = await get_policy_bundle_state(session, revision=target_revision)
    return await replace_policy_bundle_state(
        session,
        expected_revision=expected_revision,
        approved_provider_ids=target.approved_provider_ids,
        blocked_component_keys=target.blocked_component_keys,
        blocked_template_keys=target.blocked_template_keys,
        blocked_model_keys=target.blocked_model_keys,
        actor_user_id=actor_user_id,
        reason=reason or f"Rollback to policy bundle revision {target_revision}",
        rollback_of_revision=target_revision,
        source="rollback",
    )


async def bootstrap_policy_bundle_if_pristine(
    session: AsyncSession,
    *,
    approved_provider_ids: Collection[str],
    blocked_component_keys: Collection[str],
    blocked_template_keys: Collection[str],
    blocked_model_keys: Collection[str] = (),
    reason: str | None = None,
) -> tuple[PolicyBundleSnapshot, bool]:
    """Initialize a migration-created pristine bundle exactly once.

    Concurrent replicas race through the same CAS. The loser returns the
    winner's durable revision so the caller can verify configuration equality.
    """
    current = await get_policy_bundle_state(session)
    if current.initialized:
        return current, False
    try:
        snapshot = await replace_policy_bundle_state(
            session,
            expected_revision=current.revision,
            approved_provider_ids=approved_provider_ids,
            blocked_component_keys=blocked_component_keys,
            blocked_template_keys=blocked_template_keys,
            blocked_model_keys=blocked_model_keys,
            actor_user_id=None,
            reason=reason or "Bootstrap policy bundle from deployment environment",
            source="environment",
            require_uninitialized=True,
        )
    except PolicyBundleRevisionConflictError:
        return await get_policy_bundle_state(session), False
    return snapshot, True


def apply_policy_bundle_state(snapshot: PolicyBundleSnapshot) -> bool:
    """Publish a committed bundle locally with one catalog-owned reference swap."""
    from lfx.services.deps import (
        get_catalog_policy_service,
        get_model_provider_policy_service,
        get_policy_bundle_service,
    )

    catalog_service = get_catalog_policy_service()
    if catalog_service.external_policy_snapshot is None and not catalog_service.supports_policy_bundle_updates:
        msg = (
            "Configured catalog policy service does not support shared policy bundle updates; "
            "upgrade the plugin before applying database-backed policy"
        )
        raise PolicyBundleApplicationNotSupportedError(msg)

    policy_bundle_service = get_policy_bundle_service()
    bundle_changed = policy_bundle_service.publish(snapshot)
    authoritative_snapshot = policy_bundle_service.snapshot

    catalog_changed = False
    if catalog_service.external_policy_snapshot is None:
        # Built-ins share policy_bundle_service, making this an idempotent
        # same-revision publication. The explicit hook keeps independently
        # implemented database-owned plugins synchronized as well.
        catalog_changed = catalog_service.apply_policy_bundle(authoritative_snapshot)

    provider_service = get_model_provider_policy_service()
    if provider_service.external_approved_provider_ids is not None:
        return bundle_changed or catalog_changed

    if isinstance(provider_service, ModelProviderPolicyService):
        if provider_service.policy_bundle_service is None:
            provider_changed = provider_service.set_approved_provider_ids(
                authoritative_snapshot.approved_provider_ids,
                version=authoritative_snapshot.revision,
            )
        else:
            provider_changed = bundle_changed
            if provider_changed:
                provider_service.invalidate()
        return bundle_changed or catalog_changed or provider_changed

    # DB-owned policy plugins may derive provider decisions from the catalog
    # service's shared bundle snapshot. Invalidate contextual decision caches.
    if bundle_changed or catalog_changed:
        provider_service.invalidate()
    return bundle_changed or catalog_changed


async def hydrate_policy_bundle(session: AsyncSession) -> PolicyBundleSnapshot:
    """Load and publish the active complete policy revision."""
    snapshot = await get_policy_bundle_state(session)
    apply_policy_bundle_state(snapshot)
    return snapshot


__all__ = [
    "PolicyBundleApplicationNotSupportedError",
    "PolicyBundleNotInitializedError",
    "PolicyBundleRevisionConflictError",
    "apply_policy_bundle_state",
    "bootstrap_policy_bundle_if_pristine",
    "ensure_policy_bundle_application_supported",
    "get_policy_bundle_state",
    "hydrate_policy_bundle",
    "list_policy_bundle_history",
    "policy_bundle_content_hash",
    "replace_policy_bundle_state",
    "rollback_policy_bundle_state",
]
