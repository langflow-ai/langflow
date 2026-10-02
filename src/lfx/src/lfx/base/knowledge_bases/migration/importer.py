"""Replay-safe precomputed-vector import into an unpublished SQLite generation.

The application coordinator owns stopped-writer barriers, source snapshots,
authorization, exclusive generation access and final routing CAS. This module
never activates a destination or invokes an embedding provider. A receipt is
evidence of a completed copy, not permission to expose it to ordinary writers.
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from .protocol import PROTOCOL_VERSION, MigrationProtocolError

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend

    from .protocol import QualifiedExport

_T = TypeVar("_T")


async def _run_worker(function: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
    """Keep staging files and the caller's fence alive until a worker exits."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            if not cancelled:
                raise
    if cancelled:
        # Consume a possible worker exception without releasing the fence early.
        task.exception()
        raise asyncio.CancelledError
    return task.result()


@dataclass(frozen=True)
class MigrationReceipt:
    """Verification evidence for the coordinator's later routing transaction."""

    migration_id: UUID
    source_fingerprint: str
    records_sha256: str
    count: int
    store_id: str
    owner_id: str
    kb_id: str
    generation: int


def _manifest(source: QualifiedExport, migration_id: UUID, target: dict[str, Any]) -> dict[str, Any]:
    """Build target migration evidence from the fully qualified source export."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "migration_id": str(migration_id),
        "source_fingerprint": source.header.source_fingerprint,
        "source_id": source.header.source_id,
        "source_version": source.header.source_version,
        "header_sha256": source.manifest.header_sha256,
        "records_sha256": source.manifest.records_sha256,
        "count": source.manifest.count,
        "store_id": target["store_id"],
        "owner_id": target["owner_id"],
        "kb_id": target["kb_id"],
        "generation": target["generation"],
    }


def _validate_target(source: QualifiedExport, target: dict[str, Any], *, final: bool) -> None:
    """Verify that the target identity and embedding schema match the qualified source."""
    if target.get("lifecycle") != "active":
        msg = "Migration target generation is not active"
        raise MigrationProtocolError(msg)
    if (
        target.get("metric") != source.header.metric
        or target.get("model_fingerprint") != source.header.model_fingerprint
    ):
        msg = "Migration target metric or embedding-model identity differs from source"
        raise MigrationProtocolError(msg)
    dimensions = target.get("dimension")
    if dimensions is not None and dimensions != source.header.dimensions:
        msg = "Migration target dimensions differ from source"
        raise MigrationProtocolError(msg)
    if final and source.header.dimensions is not None and dimensions != source.header.dimensions:
        msg = "Migration target did not preserve source dimensions"
        raise MigrationProtocolError(msg)


async def import_qualified_export(
    source: QualifiedExport,
    backend: SQLiteBackend,
    *,
    migration_id: UUID,
    batch_size: int = 500,
    max_batch_bytes: int = 16 * 1024 * 1024,
) -> MigrationReceipt:
    """Import or replay a fully qualified source into a fenced generation.

    A new target must be empty. A partial target must have the exact same
    durable migration identity. Replay upserts the complete source rather than
    trusting a last-batch checkpoint that might outlive a failed transaction.
    Full destination comparison rejects unexpected rows and masking iterators.

    The coordinator must hold the exclusive generation guard for this entire
    call and must not publish this generation before it receives a receipt.
    On cancellation or failure the generation remains unpublished with an
    importing manifest. No caller may infer completion from a record count.
    """
    if not isinstance(migration_id, UUID):
        msg = "Migration ID must be a UUID"
        raise MigrationProtocolError(msg)
    # Validate batch bounds before mutation, including a closed source ledger.
    first = await _run_worker(source.read_batch, 0, batch_size=batch_size, max_batch_bytes=max_batch_bytes)
    target = await backend.inspect_store()
    _validate_target(source, target, final=False)
    identity = _manifest(source, migration_id, target)
    stored = await backend.read_migration_manifest()
    complete = {**identity, "status": "complete"}
    importing = {**identity, "status": "importing"}
    if stored is None:
        if await backend.count() != 0:
            msg = "A migration target without a matching manifest must be empty"
            raise MigrationProtocolError(msg)
        await backend.save_migration_manifest(importing)
    elif stored not in (importing, complete):
        msg = "Migration target belongs to a different source or migration"
        raise MigrationProtocolError(msg)

    await backend.set_migration_dimension(source.header.dimensions)

    if stored != complete:
        offset = 0
        batch = first
        while batch:
            # Native IDs were required by qualification. This reuses the common
            # precomputed bridge without its ordinary missing-ID fallback.
            await backend.add_embedded_documents(batch)
            offset += len(batch)
            batch = await _run_worker(source.read_batch, offset, batch_size=batch_size, max_batch_bytes=max_batch_bytes)
        if offset != source.manifest.count:
            msg = "Qualified source staging returned an incomplete record set"
            raise MigrationProtocolError(msg)

    if await backend.count() != source.manifest.count:
        msg = "Destination count differs from complete source export"
        raise MigrationProtocolError(msg)
    seen_count = 0
    with tempfile.TemporaryDirectory(prefix="lf-kb-verify-") as directory:
        seen_path = Path(directory) / "seen.sqlite3"
        async for batch in backend.iter_documents(
            batch_size=batch_size, include_embeddings=True, max_batch_bytes=max_batch_bytes
        ):
            await _run_worker(source.verify_batch, batch, seen_path)
            seen_count += len(batch)
            if seen_count > source.manifest.count:
                msg = "Destination iterator exceeds source count"
                raise MigrationProtocolError(msg)
    if seen_count != source.manifest.count or await backend.count() != source.manifest.count:
        msg = "Destination iterator returned an incomplete record set"
        raise MigrationProtocolError(msg)
    final_header = await backend.inspect_store()
    _validate_target(source, final_header, final=True)
    if _manifest(source, migration_id, final_header) != identity:
        msg = "Migration target identity changed during verification"
        raise MigrationProtocolError(msg)
    await backend.integrity_check()
    await backend.finalize_migration(complete)
    if await backend.read_migration_manifest() != complete:
        msg = "Migration completion manifest was not durably recorded"
        raise MigrationProtocolError(msg)
    return MigrationReceipt(
        migration_id=migration_id,
        source_fingerprint=source.header.source_fingerprint,
        records_sha256=source.manifest.records_sha256,
        count=source.manifest.count,
        store_id=target["store_id"],
        owner_id=target["owner_id"],
        kb_id=target["kb_id"],
        generation=target["generation"],
    )
