"""Background task for Memory Base ingestion.

Design principles enforced here:
- Cursor atomicity: cursor_id is NEVER updated before ingestion confirms success.
- Retry safety: If a job fails, cursor_id remains at the last known good position.
- Serialization: A per-(memory_base_id, session_id) distributed lock prevents concurrent
  jobs from racing to write the same messages into Chroma. Uses PostgreSQL advisory locks
  for cross-worker safety, with an in-process asyncio.Lock fallback for SQLite (dev/test).
  The lock is acquired before any DB or Chroma access and released in a finally block.
- Live cursor: After acquiring the lock, the current cursor_id is re-read from the DB
  (not the dispatch-time snapshot) so the pending message fetch always starts from the
  true latest position, even if a prior job advanced the cursor while this job waited.
- Path safety: kb_path is validated against kb_root before any filesystem operation.

The actual Chroma write logic is shared with KB file ingestion via
``KBIngestionHelper.write_documents_to_chroma`` — no duplicate batching/retry code here.

Document building and KB metadata sync live in ``document_builders.py``.
"""

from __future__ import annotations

import asyncio
import hashlib
import types
import weakref
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from langchain_chroma import Chroma
from lfx.base.vectorstores.chroma_security import chroma_langchain_collection_kwargs
from lfx.log.logger import logger
from sqlalchemy import text
from sqlmodel import Session, col, select

from langflow.api.utils.kb_helpers import KBIngestionHelper, KBStorageHelper
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
    sync_kb_metadata,
)
from langflow.services.memory_base.kb_path_helpers import hash_session_id, validate_kb_path
from langflow.services.memory_base.preprocessing import DEFAULT_KILL_PHRASE, run_preprocessing

if TYPE_CHECKING:
    import uuid
    from pathlib import Path

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
    user_id: uuid.UUID
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
    user_id = request.user_id
    embedding_provider = request.embedding_provider
    embedding_model = request.embedding_model
    cursor_id = request.cursor_id
    task_job_id = request.task_job_id
    job_service = request.job_service
    preprocessing = request.preprocessing
    preproc_model = request.preproc_model
    preproc_instructions = request.preproc_instructions
    preproc_kill_phrase = request.preproc_kill_phrase or DEFAULT_KILL_PHRASE

    hashed_sid = hash_session_id(session_id)
    await logger.adebug(
        "Ingestion job started | memory_base=%s session=%s dispatch_cursor=%s job=%s",
        memory_base_id,
        hashed_sid,
        cursor_id,
        task_job_id,
    )
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        msg = "Knowledge base root path is not configured"
        raise RuntimeError(msg)

    kb_path: Path = kb_root / kb_username / kb_name

    # ---- Path traversal guard ----
    validate_kb_path(kb_root, kb_path)

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
                        user_id=user_id,
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
                )
            else:
                documents = build_documents_from_messages(
                    messages, session_id=session_id, flow_id=str(flow_id), job_id=job_id_str
                )

            if not documents:
                return {"message": "No non-empty messages to ingest", "ingested": 0}

            # ---- 3. Check cancellation before touching the vector store ----
            if await KBIngestionHelper.is_job_cancelled(job_service, task_job_id):
                return {"message": "Job cancelled before ingestion", "ingested": 0}

            # ---- 4. Open Chroma, write, then sync KB metadata ----
            user_stub = types.SimpleNamespace(id=user_id)
            embeddings = await KBIngestionHelper.build_embeddings(embedding_provider, embedding_model, user_stub)

            client = KBStorageHelper.get_fresh_chroma_client(kb_path)
            written = 0
            try:
                chroma = Chroma(
                    client=client,
                    embedding_function=embeddings,
                    collection_name=kb_name,
                    **chroma_langchain_collection_kwargs(),
                )

                written = await KBIngestionHelper.write_documents_to_chroma(
                    documents=documents,
                    chroma=chroma,
                    task_job_id=task_job_id,
                    job_service=job_service,
                )

                if written == len(documents):
                    await asyncio.to_thread(sync_kb_metadata, kb_path=kb_path, chroma=chroma)
            except Exception:
                await logger.aerror(
                    "Ingestion write failed | memory_base=%s session=%s job=%s. Rolling back partial writes...",
                    memory_base_id,
                    hashed_sid,
                    task_job_id,
                )
                await KBIngestionHelper.cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
                raise
            finally:
                KBStorageHelper.release_chroma_resources(kb_path)

            if written < len(documents):
                await logger.awarning("Ingestion job %s was cancelled. Cleaning up partial data...", task_job_id)
                await KBIngestionHelper.cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
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
