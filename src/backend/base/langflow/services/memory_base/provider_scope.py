"""Trusted model-provider scope resolution for Memory Base work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.services.model_provider_policy import ModelProviderPolicyPurpose, aresolve_model_provider_policy
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.memory_base.embedding_helpers import infer_llm_provider
from langflow.services.model_provider_policy_scope import scoped_model_provider_policy_for_flow

if TYPE_CHECKING:
    import uuid

    from lfx.services.model_provider_policy import ModelProviderPolicySnapshot
    from sqlmodel.ext.asyncio.session import AsyncSession


class MemoryBaseFlowNotFoundError(PermissionError):
    """Raised when a Memory Base cannot resolve its owned stored Flow."""


@dataclass(frozen=True, slots=True)
class MemoryProviderScope:
    """Server-resolved identity and Flow domain used for provider policy."""

    memory_base: MemoryBase
    flow: Flow
    actor_user_id: uuid.UUID
    is_superuser: bool


@dataclass(frozen=True, slots=True)
class MemoryProviderPolicies:
    """Actor-scoped USE decisions reused by credential-owner call sites."""

    embedding: ModelProviderPolicySnapshot
    preprocessing: ModelProviderPolicySnapshot | None = None
    preprocessing_provider: str | None = None


async def resolve_owned_memory_flow(
    db: AsyncSession,
    *,
    flow_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Flow:
    """Load an owned Flow without accepting workspace or project input."""
    result = await db.exec(select(Flow).where(Flow.id == flow_id).where(Flow.user_id == user_id))
    flow = result.first()
    if flow is None:
        msg = f"Flow {flow_id} not found"
        raise MemoryBaseFlowNotFoundError(msg)
    return flow


async def resolve_memory_provider_scope(
    db: AsyncSession,
    *,
    memory_base_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    memory_base: MemoryBase | None = None,
) -> MemoryProviderScope:
    """Freshly resolve a Memory Base, owned Flow, and active policy actor."""
    if memory_base is None:
        result = await db.exec(
            select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == owner_user_id)
        )
        memory_base = result.first()
    if memory_base is None:
        msg = f"MemoryBase {memory_base_id} not found"
        raise MemoryBaseFlowNotFoundError(msg)

    flow = await resolve_owned_memory_flow(db, flow_id=memory_base.flow_id, user_id=owner_user_id)
    actor = await db.get(User, actor_user_id)
    if actor is None or not actor.is_active:
        msg = "Memory provider actor is inactive or no longer exists"
        raise MemoryBaseFlowNotFoundError(msg)
    return MemoryProviderScope(
        memory_base=memory_base,
        flow=flow,
        actor_user_id=actor_user_id,
        is_superuser=bool(actor.is_superuser),
    )


async def preflight_memory_provider_use(
    scope: MemoryProviderScope,
    *,
    embedding_provider: str,
    preprocessing: bool,
    preproc_model: str | None,
) -> MemoryProviderPolicies:
    """Authorize every provider a Memory job can use before any owner secret."""
    if preprocessing and not preproc_model:
        msg = "preprocessing=True but preproc_model is not set"
        raise RuntimeError(msg)
    preprocessing_provider = infer_llm_provider(preproc_model) if preprocessing and preproc_model else None
    with scoped_model_provider_policy_for_flow(
        scope.flow,
        user_id=scope.actor_user_id,
        is_superuser=scope.is_superuser,
    ):
        embedding_policy = await aresolve_model_provider_policy(
            user_id=scope.actor_user_id,
            providers=[embedding_provider],
            purpose=ModelProviderPolicyPurpose.USE,
        )
        embedding_policy.require(embedding_provider)
        preprocessing_policy = None
        if preprocessing_provider is not None:
            preprocessing_policy = await aresolve_model_provider_policy(
                user_id=scope.actor_user_id,
                providers=[preprocessing_provider],
                purpose=ModelProviderPolicyPurpose.USE,
            )
            preprocessing_policy.require(preprocessing_provider)
    return MemoryProviderPolicies(
        embedding=embedding_policy,
        preprocessing=preprocessing_policy,
        preprocessing_provider=preprocessing_provider,
    )


__all__ = [
    "MemoryBaseFlowNotFoundError",
    "MemoryProviderPolicies",
    "MemoryProviderScope",
    "preflight_memory_provider_use",
    "resolve_memory_provider_scope",
    "resolve_owned_memory_flow",
]
