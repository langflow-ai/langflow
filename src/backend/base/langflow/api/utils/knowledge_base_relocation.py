"""Move knowledge base vectors from one backend to another.

Copies each knowledge base's chunks with their existing vectors, so no embedding
model is called, then repoints the ``knowledge_base`` row at the new store. Memory
bases need no separate pass: each one refers to a ``knowledge_base`` row by
``kb_name``, and moved chunks keep their ids, so ingestion records stay valid.

Nothing is deleted from the source. A knowledge base is repointed only after the
copy is confirmed complete, so a failure at any step leaves its row pointing at
data that is still there.

Nothing may ingest into a knowledge base or capture memories while it moves. A
change seen during the copy stops the repoint. The last count and the repoint
hold the knowledge base's storage lock, so a write through the storage runtime
cannot land on the old store after the repoint. A process that writes to the
store directly, around that runtime, still can.
"""

from __future__ import annotations

import asyncio
import math
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from lfx.base.knowledge_bases.backends import BackendType, create_backend, get_backend_class
from lfx.base.knowledge_bases.backends.base import BackendConfigurationError
from lfx.log.logger import logger
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import select, update

from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord, KnowledgeBaseStatus
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.knowledge_base_storage.runtime import operation, unfenced_backend

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from uuid import UUID

    from lfx.base.knowledge_bases.backends import BaseVectorStoreBackend

RelocationStatus = Literal["relocated", "would_relocate", "skipped", "failed"]

# Inspect every source vector in bounded batches before allowing a metric change.
_METRIC_BATCH_SIZE = 100
_UNIT_NORM_TOLERANCE = 1e-3
_UNIT_EQUIVALENT_METRICS = {"cosine", "l2", "inner_product"}
_OPENSEARCH_SPACE_TYPES = {"cosine": "cosinesimil", "l2": "l2", "inner_product": "innerproduct"}

# What a write or a count raises when the target cannot be reached, by the type
# each driver has for it.
_UNREACHABLE: tuple[type[Exception], ...] = (OperationalError,)
with suppress(ImportError):
    from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError

    _UNREACHABLE = (*_UNREACHABLE, OpenSearchConnectionError)

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
    # A stable name for why it failed, for callers that cannot match on ``reason``.
    code: str | None = None
    # How to get past a metric refusal: the flag that accepts the change and, for a
    # target whose new index can take the source's metric, the config that avoids it.
    flag: str | None = None
    target_config: dict[str, Any] | None = None


def validate_relocation_target_config(target_backend_type: str, target_backend_config: dict[str, Any]) -> None:
    """Reject targets a knowledge base cannot move to, and overrides that would route multiple KBs into one store."""
    if target_backend_type == "sqlite":
        msg = (
            "--to sqlite is not a relocation target: knowledge bases are already stored in local SQLite, "
            "and relocate-kb moves them to a shared store such as postgres or opensearch"
        )
        raise ValueError(msg)
    if target_backend_type == "chroma":
        msg = "--to chroma is not a relocation target: this Langflow no longer stores knowledge bases in Chroma"
        raise ValueError(msg)
    if target_backend_type == "opensearch" and target_backend_config.get("index_name"):
        msg = "--target-config cannot set index_name: relocation needs a separate OpenSearch index for each KB"
        raise ValueError(msg)


async def relocate_knowledge_bases(
    *,
    target_backend_type: str,
    target_backend_config: dict[str, Any],
    username: str | None = None,
    dry_run: bool = False,
    batch_size: int = 500,
    allow_metric_change: bool = False,
    on_result: Callable[[KBRelocationResult], None] | None = None,
    on_progress: Callable[[KBRelocationResult], None] | None = None,
) -> list[KBRelocationResult]:
    """Relocate every knowledge base, or one user's, to the target backend.

    Returns one result per knowledge base and never raises for a single
    knowledge base's failure, so one bad store does not stop the rest.

    ``on_result`` is called with each result as its knowledge base finishes, and
    ``on_progress`` with the result so far after each batch of chunks is copied.
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
            allow_metric_change=allow_metric_change,
            on_progress=on_progress,
        )
        results.append(result)
        if on_result:
            on_result(result)
    return results


async def _relocate_one(
    record: KnowledgeBaseRecord,
    owner: str,
    *,
    target_backend_type: str,
    target_backend_config: dict[str, Any],
    dry_run: bool,
    batch_size: int,
    allow_metric_change: bool,
    on_progress: Callable[[KBRelocationResult], None] | None = None,
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
    if not_ready := _storage_not_ready(record):
        result.code = "kb_upgrade_pending"
        result.reason = not_ready
        return result
    if record.status == KnowledgeBaseStatus.INGESTING.value:
        result.code = "kb_ingesting"
        result.reason = "knowledge base is ingesting; wait for it to finish, then re-run"
        return result

    source: BaseVectorStoreBackend | None = None
    target: BaseVectorStoreBackend | None = None
    try:
        with _failing_as(result, "kb_backend_missing"):
            get_backend_class(record.backend_type)
            get_backend_class(target_backend_type)
        source = unfenced_backend(record)
        with _failing_as(result, "kb_target_unreachable"):
            target = _build_backend(target_backend_type, target_backend_config, record)
        await source.ensure_ready()
        if type(source) is type(target):
            # A stored config usually carries keys the target config leaves out (field
            # names, TLS flags) while naming the same store, so compare where the two
            # resolve to. Copying a knowledge base onto itself rewrites it in place.
            with _failing_as(result, "kb_target_unreachable"):
                await target.ensure_ready()
            if source.store_location is not None and source.store_location == target.store_location:
                result.status = "skipped"
                result.reason = "already on the target backend"
                return result
        if not record.model_selection:
            # Copying the vectors is still correct. Querying them later is not
            # guaranteed: embedding resolution falls back to a default model when the
            # row records none, and that default may not be what produced them.
            result.warnings.append(
                "model_selection is empty, so the embedding model that produced these vectors is unknown"
            )
        result.source_count = await source.count()
        if result.source_count < record.chunks:
            # Fewer chunks than recorded is what a truncated or half-lost store
            # looks like. Copying what is left and repointing would make the loss
            # permanent, so this needs a person to look first.
            result.code = "kb_short"
            result.reason = f"source holds {result.source_count} of {record.chunks} recorded chunks; not relocating"
            return result
        if result.source_count > record.chunks:
            result.warnings.append(
                f"row caches {record.chunks} chunks but the source holds {result.source_count}; using the source"
            )
        metric_problem = await _metric_change(source, target, result, allow=allow_metric_change)
        if metric_problem:
            result.reason = metric_problem
            return result
        if dry_run:
            with _failing_as(result, "kb_target_unreachable"):
                connection = await target.test_connection()
            if not connection.ok:
                result.code = "kb_target_unreachable"
                result.reason = f"target is not reachable: {connection.message}"
                return result
            result.status = "would_relocate"
            return result

        # The first write would resolve the target's connection settings. Doing it
        # here tells a target that is not set up apart from a write that failed.
        with _failing_as(result, "kb_target_unreachable"):
            await target.ensure_ready()
        async for batch in source.iter_documents(batch_size=batch_size, include_embeddings=True):
            if any(doc.embedding is None for doc in batch):
                result.code = "kb_no_vectors"
                result.reason = "source returned chunks without vectors, so they can only be re-ingested"
                return result
            with _failing_as(result, "kb_target_unreachable", _UNREACHABLE):
                await target.add_embedded_documents(batch)
            result.copied += len(batch)
            if on_progress:
                on_progress(result)

        # A read that stops early returns a short list without raising on some
        # backends, so the copy is checked against the source's own count.
        if result.copied != result.source_count:
            result.code = "kb_read_short"
            result.reason = f"read {result.copied} of {result.source_count} chunks from the source; not repointing"
            return result

        with _failing_as(result, "kb_target_unreachable", _UNREACHABLE):
            result.target_count = await _settled_count(target, result.source_count)
        if result.target_count != result.source_count:
            # More than the source means the target already held other chunks
            # (a store left from an earlier move, say), which would join this KB.
            result.code = "kb_target_more"
            result.reason = (
                f"target holds {result.target_count} chunks, the source {result.source_count}; not repointing"
            )
            return result

        # Every write through the storage runtime holds this lock, so a write under
        # way finishes before the last count, and one that starts after the repoint
        # sees the new routing and is refused.
        async with operation(record):
            # A read can page past chunks written after it started, so the copy and
            # the target can agree while the source has moved on.
            source_now = await source.count()
            if source_now != result.source_count:
                result.code = "kb_changed"
                result.reason = (
                    f"source changed during the copy ({result.source_count} -> {source_now} chunks); "
                    "stop ingestion and memory capture, then re-run"
                )
                return result

            repoint = await _repoint(record, target_backend_type, target_backend_config, result.source_count)
        if repoint == "deleted":
            result.code = "kb_deleted"
            result.reason = "knowledge base was deleted during the move"
            return result
        if repoint == "changed":
            result.code = "kb_routing_changed"
            result.reason = (
                "knowledge base's storage changed during the move (its backend, configuration, storage generation "
                "or storage state is no longer what was copied). Its current routing was preserved. Re-run."
            )
            return result
        result.status = "relocated"
    except Exception as exc:  # noqa: BLE001 - reported per knowledge base
        became = None if result.code else await _row_since_read(record)
        if became == "deleted":
            # Deleting a knowledge base retires its store before its row, so a copy
            # still reading it fails before the repoint could find the row gone.
            result.code = "kb_deleted"
            result.reason = "knowledge base was deleted during the move"
        else:
            # The storage lock refuses a row that was rerouted, with the error it has
            # for any row it cannot use, before the repoint could find it changed.
            result.code = result.code or ("kb_routing_changed" if became == "changed" else "kb_failed")
            result.reason = _describe(exc)
            await logger.awarning("Relocating knowledge base %s for %s failed: %s", record.name, owner, result.reason)
    finally:
        for backend in (source, target):
            if backend is not None:
                await backend.teardown()
    return result


def _storage_not_ready(record: KnowledgeBaseRecord) -> str | None:
    """Why the row's store cannot be read yet, or None when it can.

    A Langflow 1.13 server upgrades local Chroma knowledge bases to SQLite at
    startup. Until a row's upgrade finishes, it still names Chroma or its storage
    is not ready, and relocate-kb does not read Chroma.
    """
    state = record.storage_state
    if record.backend_type == "chroma" and (record.backend_config or {}).get("mode", "local") != "local":
        return (
            "it is a Chroma Cloud knowledge base, which this Langflow can neither read nor upgrade, "
            "so it cannot be moved from here; its data is still in Chroma Cloud"
        )
    if record.backend_type == "chroma" or state in ("migrating", "needs_attention"):
        return (
            f"its storage upgrade to SQLite has not finished (backend {record.backend_type}, storage_state {state}); "
            "start this Langflow version once with a single worker and wait until "
            "/healthz?require_storage_ready=true returns 200, or retry the upgrade from the storage status API "
            "(/api/v1/knowledge-base-storage/status), then re-run"
        )
    if state != "ready":
        return f"its storage is not ready (storage_state {state}); not relocating"
    return None


def _build_backend(
    backend_type: str,
    backend_config: dict[str, Any],
    record: KnowledgeBaseRecord,
) -> BaseVectorStoreBackend:
    # Every target is a remote store, so none needs a local path.
    return create_backend(
        backend_type,
        kb_name=record.name,
        kb_path=None,
        backend_config=backend_config,
        user_id=record.user_id,
    )


def _describe(exc: Exception) -> str:
    """Name a failure without the chunks it was handling.

    SQLAlchemy includes the statement and its parameters, and even the driver's
    first line can quote a stored value. Keep only the driver's exception type.
    """
    if not isinstance(exc, SQLAlchemyError):
        return f"{type(exc).__name__}: {exc}"
    cause = getattr(exc, "orig", None) or exc
    return f"{type(cause).__name__}: database operation failed"


@contextmanager
def _failing_as(
    result: KBRelocationResult, code: str, errors: type[Exception] | tuple[type[Exception], ...] = Exception
) -> Iterator[None]:
    """Give a failure raised inside the block ``code``, unless a narrower block already named it."""
    try:
        yield
    except errors:
        result.code = result.code or code
        raise


async def _metric_change(
    source: BaseVectorStoreBackend, target: BaseVectorStoreBackend, result: KBRelocationResult, *, allow: bool
) -> str | None:
    """Why the move would change what nearest-neighbour search returns, or None.

    Vectors keep their values across backends but not the metric they are ranked by.
    For unit-length vectors cosine, l2 and inner product rank neighbours the same way,
    so only the scores change scale, which is a warning. For any other vectors the
    ranking may change, and nothing else about the copy would show it, so it is refused
    unless ``allow`` accepts it, which leaves a warning instead.

    Checking reads every source vector, so it can also find what the copy would: a
    chunk without a vector, or a read that stops short. Each reason sets its own code.
    """
    # OpenSearch reads its metric from the index's mapping, and a mapping that does
    # not give one is what it reports as a configuration error.
    with _failing_as(result, "kb_metric_unknown", BackendConfigurationError):
        before = await source.get_distance_metric()
    # An OpenSearch target reads its metric from its cluster, which is the first
    # time a relocation needs the target's settings and a connection to it.
    with (
        _failing_as(result, "kb_target_unreachable"),
        _failing_as(result, "kb_metric_unknown", BackendConfigurationError),
    ):
        after = await target.get_distance_metric()
    if before is None or after is None or before == after:
        return None
    checked = 0
    unit_length = True
    documents = source.iter_documents(batch_size=_METRIC_BATCH_SIZE, include_embeddings=True)
    try:
        async for batch in documents:
            for doc in batch:
                if doc.embedding is None:
                    result.code = "kb_no_vectors"
                    return "source returned chunks without vectors, so they can only be re-ingested"
                checked += 1
                unit_length = unit_length and abs(math.hypot(*doc.embedding) - 1) <= _UNIT_NORM_TOLERANCE
    finally:
        if close := getattr(documents, "aclose", None):
            await close()
    if checked != result.source_count:
        result.code = "kb_read_short"
        return f"read {checked} of {result.source_count} chunks while checking metrics; not relocating"
    if not checked:
        return None
    change = f"the source ranks by {before} distance and the target by {after}"
    if unit_length and {before, after} <= _UNIT_EQUIVALENT_METRICS:
        result.warnings.append(
            f"{change}; these vectors are unit length, so the same neighbours come back but scores change scale"
        )
        return None
    uncertainty = (
        "these vectors are not unit length" if not unit_length else "these metrics may rank unit vectors differently"
    )
    if allow:
        result.warnings.append(f"{change}, and {uncertainty}, so rankings may change")
        return None
    if target.backend_type == BackendType.OPENSEARCH:
        space_type = _OPENSEARCH_SPACE_TYPES.get(before, before)
        result.target_config = {"space_type": space_type}
        how = (
            f'For a new target index, set the source\'s metric (--target-config \'{{"space_type": "{space_type}"}}\'). '
            "An existing index's metric cannot be changed by configuration; re-run with --allow-metric-change "
            "to accept the change"
        )
    else:
        how = "The target's metric is fixed; re-run with --allow-metric-change to accept the change"
    result.flag = "--allow-metric-change"
    result.code = "kb_metric_change"
    return f"{change}, and {uncertainty}, so nearest-neighbour results may change. {how}"


async def _settled_count(backend: BaseVectorStoreBackend, expected: int) -> int:
    count = await backend.count()
    for _ in range(_COUNT_SETTLE_ATTEMPTS):
        if count >= expected:
            break
        await asyncio.sleep(_COUNT_SETTLE_SECONDS)
        count = await backend.count()
    return count


async def _row_since_read(record: KnowledgeBaseRecord) -> Literal["deleted", "changed"] | None:
    """What became of the row since ``record`` was read, and None when nothing did or the database cannot say."""
    try:
        async with session_scope() as session:
            row = await session.get(KnowledgeBaseRecord, record.id)
    except SQLAlchemyError:
        return None
    if row is None or row.storage_state in ("deleting", "deleted"):
        return "deleted"
    # The columns the repoint needs unchanged.
    routing = ("user_id", "name", "backend_type", "backend_config", "storage_generation", "storage_state")
    return "changed" if any(getattr(row, column) != getattr(record, column) for column in routing) else None


async def _repoint(
    record: KnowledgeBaseRecord, backend_type: str, backend_config: dict[str, Any], chunks: int
) -> Literal["repointed", "changed", "deleted"]:
    """Point the row at the target, only if it still routes where ``record`` said when it was read.

    The storage runtime can move a row to a new generation or start deleting it
    while its chunks are copied, so the copy is only what the row names if these
    columns are unchanged. One conditional UPDATE checks and writes at once.
    Advancing the generation also invalidates handles from an earlier move to
    the same backend, even if a later move restores the original configuration.
    """
    async with session_scope() as session:
        moved = await session.exec(
            update(KnowledgeBaseRecord)
            .where(
                KnowledgeBaseRecord.id == record.id,
                KnowledgeBaseRecord.user_id == record.user_id,
                KnowledgeBaseRecord.name == record.name,
                KnowledgeBaseRecord.backend_type == record.backend_type,
                KnowledgeBaseRecord.backend_config == record.backend_config,
                KnowledgeBaseRecord.storage_generation == record.storage_generation,
                KnowledgeBaseRecord.storage_state == record.storage_state,
            )
            .values(
                backend_type=backend_type,
                backend_config=backend_config,
                chunks=chunks,
                storage_generation=record.storage_generation + 1,
            )
        )
        if moved.rowcount == 1:
            await session.commit()
            return "repointed"
        return "deleted" if await session.get(KnowledgeBaseRecord, record.id) is None else "changed"
