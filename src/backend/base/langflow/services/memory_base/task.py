"""Background task for Memory Base ingestion.

Design principles enforced here:
- Cursor atomicity: cursor_id is NEVER updated before ingestion confirms success.
- Retry safety: If a job fails, cursor_id remains at the last known good position.
- Serialization: A per-(memory_base_id, session_id) distributed lock prevents concurrent
  jobs from racing to write the same messages into the vector store. Uses PostgreSQL
  advisory locks for cross-worker safety, with an in-process asyncio.Lock fallback for
  SQLite (dev/test). The lock is acquired before any DB or vector-store access and
  released in a finally block.
- Live cursor: After acquiring the lock, the current cursor_id is re-read from the DB
  (not the dispatch-time snapshot) so the pending message fetch always starts from the
  true latest position, even if a prior job advanced the cursor while this job waited.
- Path safety: a local path is resolved only for local Chroma, and is containment-checked
  against the KB root before any filesystem operation. Remote-backed Memory Bases resolve
  no path at all.

The write goes through whichever backend the KB is configured with, resolved from the
``knowledge_base`` row — so a Memory Base on OpenSearch or Chroma Cloud ingests to that
store rather than to a local directory on whichever replica happened to run the job. The
batching/retry logic is shared with KB file ingestion via
``KBIngestionHelper.write_documents_to_backend`` — no duplicate code here.

Document building and KB metadata sync live in ``document_builders.py``.
"""

from __future__ import annotations

import asyncio
import hashlib
import weakref
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.backends import create_backend
from lfx.log.logger import logger
from lfx.workflow.end_user_identity import end_user_id_from_scoped_session
from sqlalchemy import text
from sqlmodel import Session, col, select

from langflow.api.utils.kb_helpers import (
    KBIngestionHelper,
    resolve_backend_selection,
    resolve_local_store_path,
)
from langflow.services.database.models.memory_base.model import (
    MemoryBasePreprocessingOutput,
    MemoryBaseSession,
    MemoryBaseWorkflowRun,
)
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.memory_base.document_builders import (
    build_documents_from_messages,
    build_preprocessed_document,
    sync_kb_stats_to_record,
)
from langflow.services.memory_base.kb_path_helpers import hash_session_id
from langflow.services.memory_base.preprocessing import DEFAULT_KILL_PHRASE, run_preprocessing
from langflow.services.memory_base.provider_scope import (
    MemoryProviderPolicies,
    preflight_memory_provider_use,
    resolve_memory_provider_scope,
)
from langflow.services.model_provider_policy_scope import scoped_model_provider_policy_for_flow

if TYPE_CHECKING:
    import uuid

    from lfx.services.model_provider_policy import ModelProviderPolicySnapshot

    from langflow.services.jobs.service import JobService


@dataclass(frozen=True, slots=True)
class IngestionRequest:
    """Typed parameter bundle for ``ingest_memory_task``.

    All fields needed to run an ingestion job are grouped here so callers
    construct one object instead of threading 11+ loose kwargs.
    """

    memory_base_id: uuid.UUID
    session_id: str
    flow_id: uuid.UUID
    kb_name: str
    kb_username: str
    owner_user_id: uuid.UUID
    actor_user_id: uuid.UUID
    embedding_provider: str
    embedding_model: str
    cursor_id: uuid.UUID | None
    task_job_id: uuid.UUID
    job_service: JobService
    # Preprocessing — populated from MemoryBase. When ``preprocessing`` is False the
    # remaining fields are ignored.
    preprocessing: bool = False
    preproc_model: str | None = None
    preproc_instructions: str | None = None
    preproc_kill_phrase: str | None = None


# The ingestion lock timeout is read from settings (max_ingestion_timeout_secs).
# If the timeout expires before the lock is acquired, an asyncio.TimeoutError is raised.

# ---------------------------------------------------------------------------
# Distributed locking: PostgreSQL advisory locks with in-process fallback
# ---------------------------------------------------------------------------
# In multi-worker deployments, an asyncio.Lock is process-local and cannot
# serialize across workers.  We use PostgreSQL session-level advisory locks
# keyed on a hash of (memory_base_id, session_id).  For SQLite (dev/test) we
# fall back to the in-process asyncio.Lock which is sufficient for a single worker.

_session_ingestion_locks: weakref.WeakValueDictionary[tuple, asyncio.Lock] = weakref.WeakValueDictionary()


def _get_or_create_session_lock(key: tuple) -> asyncio.Lock:
    """Return the asyncio.Lock for the given key (SQLite fallback only)."""
    lock = _session_ingestion_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _session_ingestion_locks[key] = lock
    return lock


def _compute_advisory_key(memory_base_id: uuid.UUID, session_id: str) -> int:
    """Compute a stable int64 advisory lock key from (memory_base_id, session_id)."""
    raw = f"{memory_base_id}:{session_id}".encode()
    return int(hashlib.sha256(raw).hexdigest()[:16], 16) % (2**63 - 1)


async def _is_postgres() -> bool:
    """Return True if the database backend is PostgreSQL."""
    from langflow.services.deps import get_db_service

    db_service = get_db_service()
    return db_service.engine.dialect.name == "postgresql"


async def _pg_advisory_lock(db: Session, key: int) -> None:
    """Acquire a PostgreSQL session-level advisory lock with retry and timeout.

    The lock is held on the specific connection of the shared 'db' session.
    """
    timeout = get_settings_service().settings.max_ingestion_timeout_secs
    deadline = asyncio.get_event_loop().time() + timeout
    backoff = 0.1
    max_backoff = 5.0

    while True:
        conn = await db.connection()
        result = await conn.execute(text(f"SELECT pg_try_advisory_lock({key})"))
        acquired = result.scalar()

        if acquired:
            return

        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise asyncio.TimeoutError

        await asyncio.sleep(min(backoff, remaining))
        backoff = min(backoff * 2, max_backoff)


async def _pg_advisory_unlock(db: Session, key: int) -> None:
    """Release a PostgreSQL session-level advisory lock on the shared session."""
    conn = await db.connection()
    await conn.execute(text(f"SELECT pg_advisory_unlock({key})"))


async def _acquire_session_lock(db: Session, memory_base_id: uuid.UUID, session_id: str) -> int | asyncio.Lock:
    """Acquire the distributed ingestion lock. Returns the key (PG) or Lock (SQLite)."""
    timeout = get_settings_service().settings.max_ingestion_timeout_secs
    if await _is_postgres():
        key = _compute_advisory_key(memory_base_id, session_id)
        await _pg_advisory_lock(db, key)
        return key
    lock = _get_or_create_session_lock((memory_base_id, session_id))
    await asyncio.wait_for(lock.acquire(), timeout=timeout)
    return lock


async def _release_session_lock(db: Session, lock_handle: int | asyncio.Lock) -> None:
    """Release the distributed ingestion lock."""
    if isinstance(lock_handle, int):
        await _pg_advisory_unlock(db, lock_handle)
    else:
        lock_handle.release()


async def _read_live_cursor(db: Session, memory_base_id: uuid.UUID, session_id: str) -> uuid.UUID | None:
    """Read current cursor_id from shared 'db' session inside the serialization lock."""
    stmt = (
        select(MemoryBaseSession.cursor_id)
        .where(MemoryBaseSession.memory_base_id == memory_base_id)
        .where(MemoryBaseSession.session_id == session_id)
    )
    result = await db.exec(stmt)
    return result.first()


async def ingest_memory_task(*, request: IngestionRequest) -> dict:
    """Re-resolve and bind trusted provider scope before distributed ingestion."""
    async with session_scope() as db:
        provider_scope = await resolve_memory_provider_scope(
            db,
            memory_base_id=request.memory_base_id,
            owner_user_id=request.owner_user_id,
            actor_user_id=request.actor_user_id,
        )

    provider_policies = await preflight_memory_provider_use(
        provider_scope,
        embedding_provider=request.embedding_provider,
        preprocessing=request.preprocessing,
        preproc_model=request.preproc_model,
    )
    with scoped_model_provider_policy_for_flow(
        provider_scope.flow,
        user_id=request.actor_user_id,
        is_superuser=provider_scope.is_superuser,
    ):
        return await _ingest_memory_task_in_scope(
            request=request,
            provider_policies=provider_policies,
        )


async def _build_embeddings_for_owner(
    *,
    provider: str,
    model: str,
    owner_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    provider_policy: ModelProviderPolicySnapshot,
):
    """Build with owner variables while preserving the actor's scoped decision."""
    if owner_user_id == actor_user_id:
        user_stub = type("MemoryCredentialOwner", (), {"id": owner_user_id})()
        return await KBIngestionHelper.build_embeddings(provider, model, user_stub)

    from lfx.base.models.unified_models import get_embeddings
    from lfx.base.models.unified_models.class_registry import (
        EMBEDDING_PARAM_MAPPINGS,
        EMBEDDING_PROVIDER_CLASS_MAPPING,
    )

    embedding_class = EMBEDDING_PROVIDER_CLASS_MAPPING.get(provider)
    param_mapping = EMBEDDING_PARAM_MAPPINGS.get(provider)
    if not embedding_class or not param_mapping:
        msg = f"Embedding provider '{provider}' is not registered"
        raise ValueError(msg)
    selected_option = {
        "name": model,
        "provider": provider,
        "category": provider,
        "icon": provider,
        "metadata": {
            "embedding_class": embedding_class,
            "param_mapping": param_mapping,
            "model_type": "embeddings",
        },
    }
    return get_embeddings(
        model=[selected_option],
        user_id=owner_user_id,
        provider_policy=provider_policy,
    )


async def _ingest_memory_task_in_scope(
    *,
    request: IngestionRequest,
    provider_policies: MemoryProviderPolicies,
) -> dict:
    """Ingest pending output messages from a session into the target Knowledge Base.

    Accepts a single ``IngestionRequest`` dataclass that bundles all required parameters.

    Serialization: acquires a per-(memory_base_id, session_id) distributed lock before
    any DB or Chroma access.  Uses PostgreSQL advisory locks for cross-worker
    serialization (multi-worker safe) with an in-process asyncio.Lock fallback for
    SQLite.  Concurrent jobs for the same session wait up to max_ingestion_timeout_secs;
    if the lock cannot be acquired in time, asyncio.TimeoutError is re-raised so
    execute_with_status records JobStatus.TIMED_OUT.

    Live cursor: after acquiring the lock, the current cursor_id is re-read from the DB.
    ``cursor_id`` on the request is the dispatch-time snapshot kept only for logging.
    """
    # Unpack for readability within the function body
    memory_base_id = request.memory_base_id
    session_id = request.session_id
    flow_id = request.flow_id
    kb_name = request.kb_name
    kb_username = request.kb_username
    owner_user_id = request.owner_user_id
    actor_user_id = request.actor_user_id
    embedding_provider = request.embedding_provider
    embedding_model = request.embedding_model
    cursor_id = request.cursor_id
    task_job_id = request.task_job_id
    job_service = request.job_service
    preprocessing = request.preprocessing
    preproc_model = request.preproc_model
    preproc_instructions = request.preproc_instructions
    preproc_kill_phrase = request.preproc_kill_phrase or DEFAULT_KILL_PHRASE

    # Serving plane: recover the end-user id from the scoped session id (the one identity
    # signal every ingestion path carries — live run, regenerate, manual trigger — since a
    # graph is not available here). None off / editor / anonymous, so nothing is stamped.
    end_user_id = end_user_id_from_scoped_session(session_id)

    hashed_sid = hash_session_id(session_id)
    await logger.adebug(
        "Ingestion job started | memory_base=%s session=%s dispatch_cursor=%s job=%s",
        memory_base_id,
        hashed_sid,
        cursor_id,
        task_job_id,
    )
    # The on-disk path is resolved later, once the backend is known — a Memory Base
    # on a remote vector store needs no local directory, so requiring one up front
    # would fail an ingestion that has no business touching this box's filesystem.

    # ---- 0. Acquire per-session serialization lock ----
    async with session_scope() as db:
        try:
            lock_handle = await _acquire_session_lock(db, memory_base_id, session_id)
        except asyncio.TimeoutError:
            await logger.awarning(
                "Ingestion lock wait timeout | memory_base=%s session=%s job=%s.",
                memory_base_id,
                hashed_sid,
                task_job_id,
            )
            raise

        try:
            # ---- 0b. Re-read live cursor inside the lock ----
            live_cursor_id = await _read_live_cursor(db, memory_base_id, session_id)
            await logger.adebug(
                "Ingestion lock acquired | memory_base=%s session=%s live_cursor=%s job=%s",
                memory_base_id,
                hashed_sid,
                live_cursor_id,
                task_job_id,
            )

            # ---- 1. Fetch pending output messages for this session ----
            messages = await _fetch_pending_messages(
                db,
                flow_id=flow_id,
                session_id=session_id,
                cursor_id=live_cursor_id,
            )
            if not messages:
                await logger.ainfo(
                    "MemoryBase %s / session %s: no pending messages, skipping.", memory_base_id, hashed_sid
                )
                return {"message": "No pending messages", "ingested": 0}

            # ---- 2. Build documents (preprocessing → Phase A; raw → direct) ----
            # ``preproc_row`` is non-None only on the preprocessing path; in Phase B
            # we flip its status from "processed" to "ingested" inside the same
            # transaction that advances the cursor.
            job_id_str = str(task_job_id)
            preproc_row: MemoryBasePreprocessingOutput | None = None

            if preprocessing:
                # Phase A — produce or resume preproc output (DB only, no KB I/O).
                preproc_row = await _get_pending_preproc_row(db, memory_base_id, session_id)

                if preproc_row is not None:
                    # Resume: restrict the working batch to the messages this row
                    # was built from.  Do NOT call the LLM again — the prior
                    # judgment (and cost) is preserved across crashes.
                    batch_ids = {str(mid) for mid in (preproc_row.source_message_ids or [])}
                    messages = [m for m in messages if str(m.id) in batch_ids]
                    if not messages:
                        # Source messages disappeared (cascade delete?) — close out
                        # the row as skipped so the cursor can advance past it.
                        await _update_preproc_row_status(
                            db, preproc_row, status="skipped", task_job_id=task_job_id, clear_output=True
                        )
                        await db.commit()
                        return {"message": "Preprocessing source messages missing", "ingested": 0}
                    output_text = preproc_row.output_text or ""
                    await logger.adebug(
                        "Resuming preprocessing row | row=%s memory_base=%s session=%s job=%s",
                        preproc_row.id,
                        memory_base_id,
                        hashed_sid,
                        task_job_id,
                    )
                else:
                    # Fresh run — call the LLM once over the entire batch.
                    if not preproc_model:
                        msg = "preprocessing=True but preproc_model is not set"
                        raise RuntimeError(msg)
                    result = await run_preprocessing(
                        messages=messages,
                        preproc_model=preproc_model,
                        preproc_instructions=preproc_instructions,
                        kill_phrase=preproc_kill_phrase,
                        owner_user_id=owner_user_id,
                        actor_user_id=actor_user_id,
                        provider_policy=provider_policies.preprocessing,
                    )
                    if result.status == "skipped":
                        # Kill phrase — record the skip, advance the cursor, but
                        # never write to Chroma. _mark_messages_ingested still
                        # runs so the same batch is not re-evaluated next job.
                        await _insert_preproc_row(
                            db,
                            memory_base_id=memory_base_id,
                            session_id=session_id,
                            job_id=task_job_id,
                            status="skipped",
                            output_text=None,
                            source_message_ids=[str(m.id) for m in messages],
                            model_used=preproc_model,
                        )
                        await _mark_messages_ingested(
                            db, messages=messages, job_id=task_job_id, memory_base_id=memory_base_id
                        )
                        await _advance_cursor(
                            db,
                            memory_base_id=memory_base_id,
                            session_id=session_id,
                            new_cursor_id=messages[-1].id,
                            ingested_count=len(messages),
                            task_job_id=task_job_id,
                        )
                        await logger.ainfo(
                            "Ingestion job finished | memory_base=%s session=%s job=%s skipped=True",
                            memory_base_id,
                            hashed_sid,
                            task_job_id,
                        )
                        return {"message": "Skipped by kill phrase", "ingested": 0, "skipped": True}
                    output_text = result.output_text
                    preproc_row = await _insert_preproc_row(
                        db,
                        memory_base_id=memory_base_id,
                        session_id=session_id,
                        job_id=task_job_id,
                        status="processed",
                        output_text=output_text,
                        source_message_ids=[str(m.id) for m in messages],
                        model_used=preproc_model,
                    )

                documents = build_preprocessed_document(
                    output_text=output_text,
                    source_message_ids=[str(m.id) for m in messages],
                    session_id=session_id,
                    flow_id=str(flow_id),
                    job_id=job_id_str,
                    preproc_output_id=str(preproc_row.id),
                    end_user_id=end_user_id,
                )
            else:
                documents = build_documents_from_messages(
                    messages, session_id=session_id, flow_id=str(flow_id), job_id=job_id_str, end_user_id=end_user_id
                )

            if not documents:
                return {"message": "No non-empty messages to ingest", "ingested": 0}

            # ---- 3. Check cancellation before touching the vector store ----
            if await KBIngestionHelper.is_job_cancelled(job_service, task_job_id):
                return {"message": "Job cancelled before ingestion", "ingested": 0}

            # ---- 4. Open the KB's vector-store backend, write, then sync metadata ----
            embeddings = await _build_embeddings_for_owner(
                provider=embedding_provider,
                model=embedding_model,
                owner_user_id=owner_user_id,
                actor_user_id=actor_user_id,
                provider_policy=provider_policies.embedding,
            )

            # Resolved from the knowledge_base row, so an ingestion running on a
            # replica that has never touched this KB's directory still writes to
            # the configured store instead of silently creating a local one.
            backend_type, backend_config = await resolve_backend_selection(user_id=owner_user_id, kb_name=kb_name)
            # ``None`` for every remote backend; only local Chroma gets a directory.
            kb_path = resolve_local_store_path(
                kb_name,
                kb_username,
                backend_type=backend_type,
                backend_config=backend_config,
            )
            backend = create_backend(
                backend_type,
                kb_name=kb_name,
                kb_path=kb_path,
                backend_config=backend_config,
                embedding_function=embeddings,
                user_id=owner_user_id,
            )
            written = 0
            try:
                await backend.ensure_ready()

                written = await KBIngestionHelper.write_documents_to_backend(
                    documents=documents,
                    backend=backend,
                    task_job_id=task_job_id,
                    job_service=job_service,
                )

                if written == len(documents):
                    await sync_kb_stats_to_record(user_id=owner_user_id, kb_name=kb_name, backend=backend)
            except Exception:
                await logger.aerror(
                    "Ingestion write failed | memory_base=%s session=%s job=%s. Rolling back partial writes...",
                    memory_base_id,
                    hashed_sid,
                    task_job_id,
                )
                await KBIngestionHelper.cleanup_chroma_chunks_by_job(
                    task_job_id,
                    kb_path,
                    kb_name,
                    backend_type=backend_type,
                    backend_config=backend_config,
                    user_id=owner_user_id,
                )
                raise
            finally:
                await backend.teardown()

            if written < len(documents):
                await logger.awarning("Ingestion job %s was cancelled. Cleaning up partial data...", task_job_id)
                await KBIngestionHelper.cleanup_chroma_chunks_by_job(
                    task_job_id,
                    kb_path,
                    kb_name,
                    backend_type=backend_type,
                    backend_config=backend_config,
                    user_id=owner_user_id,
                )
                return {"message": "Job cancelled during ingestion", "ingested": 0}

            # ---- 5. Phase B (preprocessing only) — flip preproc row to ingested ----
            # Staged in the same DB session as the ingestion-record writes and cursor
            # advance below. _advance_cursor holds the single Phase 2 commit so all
            # three writes land atomically.
            if preproc_row is not None:
                await _update_preproc_row_status(db, preproc_row, status="ingested", task_job_id=task_job_id)

            # ---- 6. Bulk-stamp ingestion metadata ----
            await _mark_messages_ingested(db, messages=messages, job_id=task_job_id, memory_base_id=memory_base_id)

            # ---- 7. Update cursor atomically ONLY after confirmed success ----
            last_message_id = messages[-1].id
            ingested_count = len(messages)
            await _advance_cursor(
                db,
                memory_base_id=memory_base_id,
                session_id=session_id,
                new_cursor_id=last_message_id,
                ingested_count=ingested_count,
                task_job_id=task_job_id,
            )

            await logger.ainfo(
                "Ingestion job finished | memory_base=%s session=%s job=%s ingested=%d preprocessed=%s",
                memory_base_id,
                hashed_sid,
                task_job_id,
                ingested_count,
                preprocessing,
            )
            return {"message": "Success", "ingested": ingested_count}

        finally:
            await _release_session_lock(db, lock_handle)


async def _fetch_pending_messages(
    db: Session,
    *,
    flow_id: uuid.UUID,
    session_id: str,
    cursor_id: uuid.UUID | None,
) -> list[MessageTable]:
    """Fetch all messages for this session that come after cursor_id using shared session.

    Excludes component error/exception messages (``error=True`` or ``category='error'``)
    so error text emitted by failing components is never indexed as legitimate
    conversation content. The cursor still advances past any newer non-error messages,
    so skipped error rows will not be reconsidered on subsequent runs.
    """
    from sqlalchemy import and_, or_

    stmt = (
        select(MessageTable)
        .where(MessageTable.flow_id == flow_id)
        .where(MessageTable.session_id == session_id)
        .where(MessageTable.error == False)  # noqa: E712
        .where(MessageTable.category != "error")
        .order_by(col(MessageTable.timestamp).asc(), col(MessageTable.id).asc())
    )
    if cursor_id is not None:
        cursor_stmt = select(MessageTable.timestamp, MessageTable.id).where(MessageTable.id == cursor_id)
        result = await db.exec(cursor_stmt)
        cursor_row = result.first()
        if cursor_row:
            cursor_ts, c_id = cursor_row
            stmt = stmt.where(
                or_(
                    col(MessageTable.timestamp) > cursor_ts,
                    and_(
                        col(MessageTable.timestamp) == cursor_ts,
                        col(MessageTable.id) > c_id,
                    ),
                )
            )

    result = await db.exec(stmt)
    return list(result.all())


async def _mark_messages_ingested(
    db: Session,
    *,
    messages: list[MessageTable],
    job_id: uuid.UUID,
    memory_base_id: uuid.UUID,
) -> None:
    """Batch-insert ingestion records for all successfully ingested messages using shared session.

    Does NOT commit — caller is responsible so this write batches atomically with the
    preproc-row flip and cursor advance in Phase 2.
    """
    from uuid import uuid4 as _uuid4

    from langflow.services.database.models.memory_base.model import MessageIngestionRecord

    ingested_at = datetime.now(timezone.utc)
    rows = [
        {
            "id": _uuid4(),
            "message_id": msg.id,
            "memory_base_id": memory_base_id,
            "job_id": job_id,
            "session_id": msg.session_id,
            "ingested_at": ingested_at,
        }
        for msg in messages
    ]
    conn = await db.connection()
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(MessageIngestionRecord).values(rows).on_conflict_do_nothing()
    else:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(MessageIngestionRecord).values(rows).on_conflict_do_nothing()
    await db.exec(stmt)  # type: ignore[call-overload]


async def _get_pending_preproc_row(
    db: Session,
    memory_base_id: uuid.UUID,
    session_id: str,
) -> MemoryBasePreprocessingOutput | None:
    """Return the oldest ``processed`` preproc row for this session, if any.

    A non-None return means a previous job's LLM output has not yet been
    written to Chroma. Phase A reuses it instead of re-invoking the LLM.
    """
    stmt = (
        select(MemoryBasePreprocessingOutput)
        .where(MemoryBasePreprocessingOutput.memory_base_id == memory_base_id)
        .where(MemoryBasePreprocessingOutput.session_id == session_id)
        .where(MemoryBasePreprocessingOutput.status == "processed")
        .order_by(col(MemoryBasePreprocessingOutput.created_at).asc())
        .limit(1)
    )
    result = await db.exec(stmt)
    return result.first()


async def _insert_preproc_row(
    db: Session,
    *,
    memory_base_id: uuid.UUID,
    session_id: str,
    job_id: uuid.UUID,
    status: str,
    output_text: str | None,
    source_message_ids: list[str],
    model_used: str,
) -> MemoryBasePreprocessingOutput:
    """Insert a fresh preproc-output row and commit so it survives a Chroma crash.

    For ``status='processed'`` this is the durable artifact that lets the next
    job retry only the KB write. For ``status='skipped'`` it's the audit record
    that the cursor advance was triggered by a kill-phrase response.
    """
    now = datetime.now(timezone.utc)
    row = MemoryBasePreprocessingOutput(
        memory_base_id=memory_base_id,
        session_id=session_id,
        job_id=job_id,
        status=status,
        output_text=output_text,
        source_message_ids=source_message_ids,
        model_used=model_used,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _update_preproc_row_status(
    db: Session,
    row: MemoryBasePreprocessingOutput,
    *,
    status: str,
    task_job_id: uuid.UUID,
    clear_output: bool = False,
) -> None:
    """Stage a status flip on a preproc row. Caller is responsible for commit.

    Used in two places:
      - Phase B success: status="ingested". The caller batches this with
        ``_advance_cursor`` so all three writes commit atomically.
      - Orphan cleanup: status="skipped" + clear_output=True when the source
        messages this row refers to no longer exist. The caller commits
        immediately because there is no follow-up batch.

    ``job_id`` is updated to ``task_job_id`` so ``cleanup_chroma_chunks_by_job``
    keys remain consistent on retry — after a failed-then-cleaned Chroma write
    the original job_id no longer matches any docs.
    """
    row.status = status
    row.job_id = task_job_id
    row.updated_at = datetime.now(timezone.utc)
    if clear_output:
        row.output_text = None
    db.add(row)


async def _advance_cursor(
    db: Session,
    *,
    memory_base_id: uuid.UUID,
    session_id: str,
    new_cursor_id: uuid.UUID,
    ingested_count: int,
    task_job_id: uuid.UUID,
) -> None:
    """Atomically advance the cursor using the shared 'db' session."""
    from sqlalchemy import update as sa_update

    stmt = (
        select(MemoryBaseSession)
        .where(MemoryBaseSession.memory_base_id == memory_base_id)
        .where(MemoryBaseSession.session_id == session_id)
    )
    result = await db.exec(stmt)
    mbs = result.first()
    if mbs is None:
        await logger.awarning(
            "MemoryBaseSession for (%s, %s) vanished before cursor update.",
            memory_base_id,
            hash_session_id(session_id),
        )
        return

    mbs.cursor_id = new_cursor_id
    mbs.total_processed += ingested_count
    mbs.last_sync_at = datetime.now(timezone.utc)
    db.add(mbs)

    # Stamp all pending workflow run rows for this session.
    await db.exec(  # type: ignore[call-overload]
        sa_update(MemoryBaseWorkflowRun)
        .where(MemoryBaseWorkflowRun.memory_base_id == memory_base_id)
        .where(MemoryBaseWorkflowRun.session_id == session_id)
        .where(MemoryBaseWorkflowRun.ingestion_job_id == None)  # noqa: E711
        .values(ingestion_job_id=task_job_id)
    )

    await db.commit()
