"""Persistence bridge for the install-wide model-provider deployment ceiling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lfx.services.deps import get_model_provider_policy_service
from lfx.services.model_provider_policy import ModelProviderPolicyService
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlmodel import select

from langflow.services.database.models.model_provider_policy import (
    MODEL_PROVIDER_POLICY_SINGLETON_ID,
    ModelProviderPolicy,
)
from langflow.services.policy_bundle import (
    PolicyBundleNotInitializedError,
    apply_policy_bundle_state,
    ensure_policy_bundle_application_supported,
    get_policy_bundle_state,
    replace_policy_bundle_state,
)

if TYPE_CHECKING:
    from collections.abc import Collection
    from uuid import UUID

    from lfx.services.policy_bundle import PolicyBundleSnapshot
    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True)
class PersistedModelProviderPolicy:
    """Immutable copy of the singleton policy row."""

    approved_provider_ids: frozenset[str]
    version: int
    bundle_snapshot: PolicyBundleSnapshot | None = field(default=None, compare=False, repr=False)


ModelProviderPolicyNotInitializedError = PolicyBundleNotInitializedError


def _policy_statement():
    return (
        select(ModelProviderPolicy)
        .where(ModelProviderPolicy.id == MODEL_PROVIDER_POLICY_SINGLETON_ID)
        .execution_options(populate_existing=True)
    )


def _replace_policy_statement(provider_ids: Collection[str]):
    table = ModelProviderPolicy.__table__
    return (
        update(table)
        .where(table.c.id == MODEL_PROVIDER_POLICY_SINGLETON_ID)
        .values(
            approved_provider_ids=sorted(set(provider_ids)),
            version=table.c.version + 1,
        )
    )


async def get_model_provider_policy_state(session: AsyncSession) -> PersistedModelProviderPolicy:
    """Read the persisted deployment ceiling.

    The migration seeds the singleton. Treating a missing row as unrestricted
    would silently remove a configured deployment ceiling, so surface a
    dedicated initialization error instead.
    """
    # Keep the provider-only read seam usable against an N-1 database while a
    # rolling deployment is applying the additive policy-bundle migration.
    # Lightweight test/plugin sessions also intentionally expose only exec().
    if not callable(getattr(session, "get", None)):
        return await _get_legacy_model_provider_policy_state(session)

    try:
        row = await get_policy_bundle_state(session)
    except DBAPIError as exc:
        if not _is_missing_policy_bundle_table(exc):
            raise
        await session.rollback()
        return await _get_legacy_model_provider_policy_state(session)
    return PersistedModelProviderPolicy(
        approved_provider_ids=frozenset(row.approved_provider_ids),
        version=row.revision,
        bundle_snapshot=row,
    )


async def _get_legacy_model_provider_policy_state(session: AsyncSession) -> PersistedModelProviderPolicy:
    row = (await session.exec(_policy_statement())).one_or_none()
    if row is None:
        msg = "Model-provider policy singleton is missing; apply the latest database migrations"
        raise ModelProviderPolicyNotInitializedError(msg)
    return PersistedModelProviderPolicy(
        approved_provider_ids=frozenset(row.approved_provider_ids),
        version=row.version,
    )


def _is_missing_policy_bundle_table(exc: DBAPIError) -> bool:
    message = str(getattr(exc, "orig", exc)).casefold()
    return "policy_bundle_active" in message and (
        "does not exist" in message or "no such table" in message or "undefined table" in message
    )


async def replace_model_provider_policy_state(
    session: AsyncSession,
    provider_ids: Collection[str],
    *,
    actor_user_id: UUID | None = None,
    reason: str | None = None,
) -> PersistedModelProviderPolicy:
    """Serialize and commit a complete replacement of the singleton policy.

    One ``UPDATE ... version = version + 1`` statement serializes writers in
    PostgreSQL and SQLite. The same transaction reads its updated state before
    commit, avoiding SQLite's newer ``RETURNING`` syntax while ensuring another
    writer cannot interleave. Concurrent replacements therefore commit complete
    sets with distinct versions.
    """
    if not callable(getattr(session, "get", None)):
        return await _replace_legacy_model_provider_policy_state(session, provider_ids)

    current = await get_model_provider_policy_state(session)
    if current.bundle_snapshot is None:
        return await _replace_legacy_model_provider_policy_state(session, provider_ids)

    bundle = current.bundle_snapshot
    ensure_policy_bundle_application_supported()
    state = await replace_policy_bundle_state(
        session,
        expected_revision=bundle.revision,
        approved_provider_ids=provider_ids,
        blocked_component_keys=bundle.blocked_component_keys,
        blocked_template_keys=bundle.blocked_template_keys,
        blocked_model_keys=bundle.blocked_model_keys,
        actor_user_id=actor_user_id,
        reason=reason,
    )
    return PersistedModelProviderPolicy(
        approved_provider_ids=state.approved_provider_ids,
        version=state.revision,
        bundle_snapshot=state,
    )


async def _replace_legacy_model_provider_policy_state(
    session: AsyncSession,
    provider_ids: Collection[str],
) -> PersistedModelProviderPolicy:
    result = await session.exec(_replace_policy_statement(provider_ids))
    if result.rowcount != 1:
        msg = "Model-provider policy singleton is missing; apply the latest database migrations"
        raise ModelProviderPolicyNotInitializedError(msg)
    state = await _get_legacy_model_provider_policy_state(session)
    await session.commit()
    return state


def apply_model_provider_policy_state(
    state: PersistedModelProviderPolicy,
    *,
    invalidate_external: bool = True,
) -> bool:
    """Publish committed state locally, returning whether this worker changed."""
    service = get_model_provider_policy_service()
    # A mixed-ownership deployment may keep provider policy external while the
    # catalog facets remain database-owned. Publish the complete bundle first;
    # apply_policy_bundle_state deliberately leaves an external provider alone.
    if state.bundle_snapshot is not None:
        return apply_policy_bundle_state(state.bundle_snapshot)

    # Explicitly external services own both their state and invalidation. This
    # check is intentionally based on ``is not None`` because an empty external
    # ceiling still establishes external ownership. Check ownership before the
    # concrete OSS type so subclasses cannot opt in and still receive DB state.
    if service.external_approved_provider_ids is not None:
        return False

    if isinstance(service, ModelProviderPolicyService):
        return service.set_approved_provider_ids(state.approved_provider_ids, version=state.version)

    # Legacy third-party services predate the explicit ownership contract. An
    # administrative write still invalidates their local snapshot, while the
    # OSS polling worker must not repeatedly disturb them.
    if invalidate_external:
        service.invalidate()
        return True
    return False


async def hydrate_model_provider_policy(session: AsyncSession) -> PersistedModelProviderPolicy:
    """Hydrate or invalidate the active policy service after database startup."""
    state = await get_model_provider_policy_state(session)
    apply_model_provider_policy_state(state)
    return state


__all__ = [
    "ModelProviderPolicyNotInitializedError",
    "PersistedModelProviderPolicy",
    "apply_model_provider_policy_state",
    "get_model_provider_policy_state",
    "hydrate_model_provider_policy",
    "replace_model_provider_policy_state",
]
