"""Trusted model-provider scope resolution for Memory Base work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    import uuid

    from sqlmodel.ext.asyncio.session import AsyncSession


class MemoryBaseFlowNotFoundError(PermissionError):
    """Raised when a Memory Base cannot resolve its owned stored Flow."""


@dataclass(frozen=True, slots=True)
class MemoryProviderScope:
    """Server-resolved identity and Flow domain used for provider policy."""

    flow: Flow
    is_superuser: bool


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
    flow_id: uuid.UUID,
    user_id: uuid.UUID,
) -> MemoryProviderScope:
    """Re-resolve the Flow domain and superuser flag from server-owned rows."""
    flow = await resolve_owned_memory_flow(db, flow_id=flow_id, user_id=user_id)
    user = await db.get(User, user_id)
    if user is None:
        msg = f"Flow {flow_id} not found"
        raise MemoryBaseFlowNotFoundError(msg)
    return MemoryProviderScope(flow=flow, is_superuser=bool(user.is_superuser))


__all__ = [
    "MemoryBaseFlowNotFoundError",
    "MemoryProviderScope",
    "resolve_memory_provider_scope",
    "resolve_owned_memory_flow",
]
