"""Persistence bridge for the install-wide model-provider deployment ceiling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.services.deps import get_model_provider_policy_service
from lfx.services.model_provider_policy import ModelProviderPolicyService
from sqlalchemy import update
from sqlmodel import select

from langflow.services.database.models.model_provider_policy import (
    MODEL_PROVIDER_POLICY_SINGLETON_ID,
    ModelProviderPolicy,
)

if TYPE_CHECKING:
    from collections.abc import Collection

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True)
class PersistedModelProviderPolicy:
    """Immutable copy of the singleton policy row."""

    approved_provider_ids: frozenset[str]
    version: int


class ModelProviderPolicyNotInitializedError(RuntimeError):
    """The singleton row required to evaluate the install-wide policy is missing."""


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
    row = (await session.exec(_policy_statement())).one_or_none()
    if row is None:
        msg = "Model-provider policy singleton is missing; apply the latest database migrations"
        raise ModelProviderPolicyNotInitializedError(msg)
    return PersistedModelProviderPolicy(
        approved_provider_ids=frozenset(row.approved_provider_ids),
        version=row.version,
    )


async def replace_model_provider_policy_state(
    session: AsyncSession,
    provider_ids: Collection[str],
) -> PersistedModelProviderPolicy:
    """Serialize and commit a complete replacement of the singleton policy.

    One ``UPDATE ... version = version + 1`` statement serializes writers in
    PostgreSQL and SQLite. The same transaction reads its updated state before
    commit, avoiding SQLite's newer ``RETURNING`` syntax while ensuring another
    writer cannot interleave. Concurrent replacements therefore commit complete
    sets with distinct versions.
    """
    result = await session.exec(_replace_policy_statement(provider_ids))
    if result.rowcount != 1:
        msg = "Model-provider policy singleton is missing; apply the latest database migrations"
        raise ModelProviderPolicyNotInitializedError(msg)
    state = await get_model_provider_policy_state(session)
    await session.commit()
    return state


def apply_model_provider_policy_state(
    state: PersistedModelProviderPolicy,
    *,
    invalidate_external: bool = True,
) -> bool:
    """Publish committed state locally, returning whether this worker changed."""
    service = get_model_provider_policy_service()
    if isinstance(service, ModelProviderPolicyService):
        return service.set_approved_provider_ids(state.approved_provider_ids, version=state.version)

    # Enterprise services own their policy source. An administrative write can
    # still invalidate their local snapshot, while the OSS polling worker must
    # not repeatedly disturb a separately managed policy implementation.
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
