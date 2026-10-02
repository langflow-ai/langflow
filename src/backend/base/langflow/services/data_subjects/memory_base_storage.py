"""Durable teardown of the vector stores behind the Memory Bases of erased flows.

Deleting a flow drops its Memory Base rows, and with them the routing to the remote collection. The
erase engine therefore stores each handle in the request's storage plan in the same transaction as
the row delete, and this step must succeed before the item leaves the plan: a failure is retried and
holds the request open, unlike the best-effort cleanup of an ordinary flow delete.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.base.knowledge_bases.backends import create_backend, is_local_chroma

if TYPE_CHECKING:
    from langflow.services.memory_base.flow_cleanup import FlowMemoryBaseCleanup

KIND_MEMORY_BASE = "memory_base"


def memory_base_items(handles: list[FlowMemoryBaseCleanup]) -> list[dict[str, Any]]:
    return [
        {
            "kind": KIND_MEMORY_BASE,
            "value": handle.kb_name,
            "user_id": str(handle.user_id),
            "kb_username": handle.kb_username,
            "backend_type": handle.backend_type,
            "backend_config": dict(handle.backend_config),
        }
        for handle in handles
    ]


async def _drop_remote_collection(item: dict[str, Any]) -> None:
    backend_type, backend_config = str(item["backend_type"]), dict(item.get("backend_config") or {})
    if is_local_chroma(backend_type, backend_config):
        return
    backend = create_backend(
        backend_type, kb_name=str(item["value"]), backend_config=backend_config, user_id=UUID(str(item["user_id"]))
    )
    try:
        await backend.ensure_ready()
        await backend.delete_collection()
    finally:
        await backend.teardown()


class MemoryBaseDirectoryNotDeletedError(RuntimeError):
    """The local directory survived; the item stays in the plan so the step is retried."""


def _remove_local_directory(kb_name: str, kb_username: str) -> None:
    # Imported here like the other storage steps: kb_helpers sits above the services layer.
    from langflow.api.utils.kb_helpers import KBStorageHelper, validate_kb_path

    try:
        root = KBStorageHelper.get_root_path()
    except ValueError:
        return
    path = root / kb_username / kb_name
    validate_kb_path(root, path)
    if path.exists() and not KBStorageHelper.delete_storage(path, kb_name):
        msg = f"Memory Base directory {kb_name} could not be deleted"
        raise MemoryBaseDirectoryNotDeletedError(msg)


async def drop_memory_base(item: dict[str, Any]) -> None:
    """Delete the remote collection, then the local directory; any failure propagates for a retry."""
    await _drop_remote_collection(item)
    if item.get("kb_username"):
        await asyncio.to_thread(_remove_local_directory, str(item["value"]), str(item["kb_username"]))
