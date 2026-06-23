"""Memory management for lfx, routed through the pluggable MEMORY_SERVICE.

Every public function resolves the registered memory service via
``get_memory_service()`` *at call time*. The question this layer asks is simply
"is a memory backend registered" — not "is langflow importable and is its DB
non-noop". Which concrete backend the registered service uses (in-memory vs a
real DB) is decided by the MEMORY_SERVICE factory/service layer, not here.

Resolution happens per call (rather than binding at import) because the service
manager — and the database service that a DB-backed backend depends on — is
typically registered *after* this module is first imported (e.g. from Component
class definitions loaded before graph setup). The call-time lookup is a cheap
manager hit that returns the already-cached service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.deps import get_memory_service

if TYPE_CHECKING:
    from lfx.services.memory.base import MemoryService


def _impl() -> MemoryService:
    """Resolve the registered memory service.

    The MEMORY_SERVICE factory is always registered (auto-discovered from the
    ``ServiceType`` enum and registered explicitly in ``lfx.services.initialize``),
    so this normally returns a real service. We guard against ``None`` only to
    fail loudly on a genuinely broken service manager rather than silently route
    memory into a throwaway store.
    """
    service = get_memory_service()
    if service is None:  # pragma: no cover - the factory is always registered
        msg = "No memory service is registered; cannot perform memory operations."
        raise RuntimeError(msg)
    return service


async def aadd_messages(*args: Any, **kwargs: Any):
    return await _impl().aadd_messages(*args, **kwargs)


async def aadd_messagetables(*args: Any, **kwargs: Any):
    return await _impl().aadd_messagetables(*args, **kwargs)


def add_messages(*args: Any, **kwargs: Any):
    return _impl().add_messages(*args, **kwargs)


async def adelete_messages(*args: Any, **kwargs: Any):
    return await _impl().adelete_messages(*args, **kwargs)


async def aget_messages(*args: Any, **kwargs: Any):
    return await _impl().aget_messages(*args, **kwargs)


async def astore_message(*args: Any, **kwargs: Any):
    return await _impl().astore_message(*args, **kwargs)


async def aupdate_messages(*args: Any, **kwargs: Any):
    return await _impl().aupdate_messages(*args, **kwargs)


async def delete_message(*args: Any, **kwargs: Any):
    return await _impl().adelete_message(*args, **kwargs)


def delete_messages(*args: Any, **kwargs: Any):
    return _impl().delete_messages(*args, **kwargs)


def get_messages(*args: Any, **kwargs: Any):
    return _impl().get_messages(*args, **kwargs)


def store_message(*args: Any, **kwargs: Any):
    return _impl().store_message(*args, **kwargs)


__all__ = [
    "aadd_messages",
    "aadd_messagetables",
    "add_messages",
    "adelete_messages",
    "aget_messages",
    "astore_message",
    "aupdate_messages",
    "delete_message",
    "delete_messages",
    "get_messages",
    "store_message",
]
