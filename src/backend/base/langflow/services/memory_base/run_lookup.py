"""Which memory base a flow run uses: the running user's own, else one a registered plane shares to it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from langflow.services.database.models.memory_base.model import MemoryBase

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

_shared_mb_for_run_enabled: Callable[[], bool] | None = None


def register_shared_mb_for_run(enabled: Callable[[], bool]) -> None:
    """Let a flow run use a memory base it does not own, when authorization shares it to the running identity.

    OSS never registers this, so a run sees only the memory bases of the user it runs as. A downstream plane registers
    it for the runs where the running identity is not the owner (a deployment runs as a service account and the memory
    bases are the deployer's). ``enabled`` is asked on every lookup.
    """
    global _shared_mb_for_run_enabled  # noqa: PLW0603 - process-wide extension registration
    _shared_mb_for_run_enabled = enabled


async def find_for_run(
    db: AsyncSession, *, name: str, flow_id: UUID, user_id: UUID, action: str = "read"
) -> MemoryBase | None:
    """The memory base called ``name`` attached to ``flow_id`` that ``user_id`` runs with.

    The user's own row first. Otherwise the one row, attached to the same flow, that authorization lets ``user_id``
    ``action`` (a memory base is authorized as a knowledge base, by its own id). ``None`` when nothing is registered,
    authorization is off, or no candidate allows ``action``. Two allowed candidates are refused as ambiguous rather
    than picking one.
    """
    base = select(MemoryBase).where(MemoryBase.name == name, MemoryBase.flow_id == flow_id)
    own = (await db.exec(base.where(MemoryBase.user_id == user_id))).first()
    if own is not None or _shared_mb_for_run_enabled is None or not _shared_mb_for_run_enabled():
        return own

    from langflow.services.auth.context import current_auth_context_for_authz
    from langflow.services.deps import get_authorization_service

    authz = get_authorization_service()
    if not (await authz.is_enabled() and await authz.supports_cross_user_fetch()):
        return None
    candidates = (await db.exec(base.where(MemoryBase.user_id != user_id))).all()
    allowed = [
        candidate
        for candidate in candidates
        if await authz.enforce(
            user_id=user_id,
            domain="*",
            obj=f"knowledge_base:{candidate.id}",
            act=action,
            context={**current_auth_context_for_authz(), "is_superuser": False},
        )
    ]
    if len(allowed) > 1:
        msg = f"Several memory bases named '{name}' are shared with this identity; use an owned one with that name."
        raise ValueError(msg)
    return allowed[0] if allowed else None
