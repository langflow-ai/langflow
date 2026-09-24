"""Move knowledge base vectors from one backend to another.

Copies each knowledge base's chunks with their existing vectors, so no embedding
model is called, then repoints the ``knowledge_base`` row at the new store. Memory
bases need no separate pass: each one refers to a ``knowledge_base`` row by
``kb_name``, and moved chunks keep their ids, so ingestion records stay valid.

Nothing is deleted from the source. A knowledge base is repointed only after the
copy is confirmed complete, so a failure at any step leaves its row pointing at
data that is still there.

Nothing may ingest into a knowledge base or capture memories while it moves. A
change seen during the copy stops the repoint, but a job that resolved the old
backend before the repoint can still write there afterwards.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from lfx.base.knowledge_bases.backends import create_backend
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils.kb_helpers import resolve_local_store_path
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord, KnowledgeBaseStatus
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.base.knowledge_bases.backends import BaseVectorStoreBackend

RelocationStatus = Literal["relocated", "would_relocate", "skipped", "failed"]

# Some stores (OpenSearch) count newly written chunks only after a refresh, so
# the post-copy count is polled briefly before a shortfall is treated as real.
_COUNT_SETTLE_ATTEMPTS = 10
_COUNT_SETTLE_SECONDS = 0.5


@dataclass
class KBRelocationResult:
    kb_id: UUID
    kb_name: str
    owner: str
    source_backend: str
    target_backend: str
    status: RelocationStatus
    source_count: int = 0
    copied: int = 0
    target_count: int = 0
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)


def validate_relocation_target_config(target_backend_type: str, target_backend_config: dict[str, Any]) -> None:
    """Reject collection overrides that would route multiple KBs into one store."""
    if target_backend_type == "opensearch" and "index_name" in target_backend_config:
        msg = "--target-config cannot set index_name: relocation needs a separate OpenSearch index for each KB"
        raise ValueError(msg)
    if (
        target_backend_type == "chroma"
        and str(target_backend_config.get("mode", "local")).lower() == "cloud"
        and "collection_name" in target_backend_config
    ):
        msg = (
            "--target-config cannot set collection_name: "
            "relocation needs a separate Chroma Cloud collection for each KB"
        )
        raise ValueError(msg)


async def relocate_knowledge_bases(
    *,
    target_backend_type: str,
    target_backend_config: dict[str, Any],
    username: str | None = None,
    dry_run: bool = False,
    batch_size: int = 500,
) -> list[KBRelocationResult]:
    """Relocate every knowledge base, or one user's, to the target backend.

    Returns one result per knowledge base and never raises for a single
    knowledge base's failure, so one bad store does not stop the rest.
    """
    validate_relocation_target_config(target_backend_type, target_backend_config)
    async with session_scope() as session:
        stmt = select(KnowledgeBaseRecord, User.username).join(User, User.id == KnowledgeBaseRecord.user_id)
        if username:
            stmt = stmt.where(User.username == username)
        rows = list((await session.exec(stmt)).all())

    results = []
    for record, owner in rows:
        result = await _relocate_one(
            record,
            owner,
            target_backend_type=target_backend_type,
            target_backend_config=target_backend_config,
            dry_run=dry_run,
            batch_size=batch_size,
        )
        results.append(result)
    return results


async def _relocate_one(
    record: KnowledgeBaseRecord,
    owner: str,
    *,
    target_backend_type: str,
    target_backend_config: dict[str, Any],
    dry_run: bool,
    batch_size: int,
) -> KBRelocationResult:
    source_config = record.backend_config or {}
    result = KBRelocationResult(
        kb_id=record.id,
        kb_name=record.name,
        owner=owner,
        source_backend=record.backend_type,
        target_backend=target_backend_type,
        status="failed",
        source_count=record.chunks,
    )
    if record.backend_type == target_backend_type and source_config == target_backend_config:
        result.status = "skipped"
        result.reason = "already on the target backend"
        return result
    if record.status == KnowledgeBaseStatus.INGESTING.value:
        result.reason = "knowledge base is ingesting; wait for it to finish, then re-run"
        return result
    if not record.model_selection:
        # Copying the vectors is still correct. Querying them later is not
        # guaranteed: embedding resolution falls back to a default model when the
        # row records none, and that default may not be what produced them.
        result.warnings.append(
            "model_selection is empty, so the embedding model that produced these vectors is unknown"
        )

    source: BaseVectorStoreBackend | None = None
    target: BaseVectorStoreBackend | None = None
    try:
        source = _build_backend(record.backend_type, source_config, record, owner)
        target = _build_backend(target_backend_type, target_backend_config, record, owner, create=not dry_run)
        await source.ensure_ready()
        result.source_count = await source.count()
        if result.source_count < record.chunks:
            # Fewer chunks than recorded is what a truncated or half-lost store
            # looks like. Copying what is left and repointing would make the loss
            # permanent, so this needs a person to look first.
            result.reason = f"source holds {result.source_count} of {record.chunks} recorded chunks; not relocating"
            return result
        if result.source_count > record.chunks:
            result.warnings.append(
                f"row caches {record.chunks} chunks but the source holds {result.source_count}; using the source"
            )
        if dry_run:
            connection = await target.test_connection()
            if not connection.ok:
                result.reason = f"target is not reachable: {connection.message}"
                return result
            result.status = "would_relocate"
            return result

        async for batch in source.iter_documents(batch_size=batch_size, include_embeddings=True):
            if any(doc.embedding is None for doc in batch):
                result.reason = "source returned chunks without vectors, so they can only be re-ingested"
                return result
            await target.add_embedded_documents(batch)
            result.copied += len(batch)

        # A read that stops early returns a short list without raising on some
        # backends, so the copy is checked against the source's own count.
        if result.copied != result.source_count:
            result.reason = f"read {result.copied} of {result.source_count} chunks from the source; not repointing"
            return result

        result.target_count = await _settled_count(target, result.source_count)
        if result.target_count != result.source_count:
            # More than the source means the target already held other chunks
            # (a store left from an earlier move, say), which would join this KB.
            result.reason = (
                f"target holds {result.target_count} chunks, the source {result.source_count}; not repointing"
            )
            return result

        # A read can page past chunks written after it started, so the copy and
        # the target can agree while the source has moved on.
        source_now = await source.count()
        if source_now != result.source_count:
            result.reason = (
                f"source changed during the copy ({result.source_count} -> {source_now} chunks); "
                "stop ingestion and memory capture, then re-run"
            )
            return result

        if not await _repoint(record.id, target_backend_type, target_backend_config, result.source_count):
            result.reason = "knowledge base was deleted during the move"
            return result
        result.status = "relocated"
    except Exception as exc:  # noqa: BLE001 - reported per knowledge base
        result.reason = f"{type(exc).__name__}: {exc}"
        await logger.awarning("Relocating knowledge base %s for %s failed: %s", record.name, owner, exc)
    finally:
        for backend in (source, target):
            if backend is not None:
                await backend.teardown()
    return result


def _build_backend(
    backend_type: str,
    backend_config: dict[str, Any],
    record: KnowledgeBaseRecord,
    owner: str,
    *,
    create: bool = False,
) -> BaseVectorStoreBackend:
    kb_path = resolve_local_store_path(
        record.name, owner, backend_type=backend_type, backend_config=backend_config, create=create
    )
    return create_backend(
        backend_type,
        kb_name=record.name,
        kb_path=kb_path,
        backend_config=backend_config,
        user_id=record.user_id,
    )


async def _settled_count(backend: BaseVectorStoreBackend, expected: int) -> int:
    count = await backend.count()
    for _ in range(_COUNT_SETTLE_ATTEMPTS):
        if count >= expected:
            break
        await asyncio.sleep(_COUNT_SETTLE_SECONDS)
        count = await backend.count()
    return count


async def _repoint(record_id: UUID, backend_type: str, backend_config: dict[str, Any], chunks: int) -> bool:
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record_id)
        if row is None:
            return False
        row.backend_type = backend_type
        row.backend_config = backend_config
        row.chunks = chunks
        session.add(row)
        await session.commit()
    return True
