"""Background task for Memory Base ingestion.

Design principles enforced here:
- Cursor atomicity: cursor_id is NEVER updated before ingestion confirms success.
- Retry safety: If a job fails, cursor_id remains at the last known good position.
- Serialization: A per-(memory_base_id, session_id) lock prevents concurrent jobs from
  racing to write the same messages into Chroma. The lock is acquired before any DB or
  Chroma access and released in a finally block.
- Live cursor: After acquiring the lock, the current cursor_id is re-read from the DB
  (not the dispatch-time snapshot) so the pending message fetch always starts from the
  true latest position, even if a prior job advanced the cursor while this job waited.

The actual Chroma write logic is shared with KB file ingestion via
``KBIngestionHelper.write_documents_to_chroma`` — no duplicate batching/retry code here.
"""

from __future__ import annotations

import asyncio
import json
import types
import weakref
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBIngestionHelper, KBStorageHelper
from langflow.services.database.models.memory_base.model import MemoryBaseSession, MemoryBaseWorkflowRun
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    import uuid
    from pathlib import Path

    from langflow.services.jobs.service import JobService

# Chunk size for splitting long messages before embedding
_MESSAGE_CHUNK_SIZE = 1000
_MESSAGE_CHUNK_OVERLAP = 100

# Per-(memory_base_id, session_id) lock registry — serializes concurrent ingestion jobs
# for the same session so that two jobs dispatched before either completes cannot race to
# write overlapping messages into Chroma. Pattern follows api/v2/mcp.py:_update_server_locks.
# WeakValueDictionary: entries are GC'd automatically once no coroutine holds a strong
# reference to the lock (i.e. after the task releases it and no other task is waiting).
_session_ingestion_locks: weakref.WeakValueDictionary[tuple, asyncio.Lock] = weakref.WeakValueDictionary()


def _get_or_create_session_lock(key: tuple) -> asyncio.Lock:
    """Return the asyncio.Lock for the given (memory_base_id, session_id) key.

    Creates a new lock if none exists.  The caller must hold a strong reference
    to the returned lock for the duration of its use so the WeakValueDictionary
    entry is not collected prematurely.  The Python GIL guarantees that the
    dict read + conditional write is effectively atomic in the async event loop.
    """
    lock = _session_ingestion_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _session_ingestion_locks[key] = lock
    return lock


# How long a job waits to acquire the session lock before timing out. When the timeout
# expires, asyncio.TimeoutError is re-raised so execute_with_status records JobStatus.TIMED_OUT.
_LOCK_WAIT_TIMEOUT_SECS: int = 600  # 10 minutes


async def _read_live_cursor(memory_base_id: uuid.UUID, session_id: str) -> uuid.UUID | None:
    """Read the current cursor_id from the DB inside the serialization lock.

    Returns the live cursor — not the dispatch-time snapshot — so the pending
    message fetch always starts from the true latest position.  Returns None if
    the session does not exist or no messages have been ingested yet.
    """
    async with session_scope() as db:
        stmt = (
            select(MemoryBaseSession.cursor_id)
            .where(MemoryBaseSession.memory_base_id == memory_base_id)
            .where(MemoryBaseSession.session_id == session_id)
        )
        result = await db.exec(stmt)
        return result.first()


async def ingest_memory_task(
    *,
    memory_base_id: uuid.UUID,
    session_id: str,
    flow_id: uuid.UUID,
    kb_name: str,
    kb_username: str,
    user_id: uuid.UUID,
    embedding_provider: str,
    embedding_model: str,
    cursor_id: uuid.UUID | None,
    task_job_id: uuid.UUID,
    job_service: JobService,
) -> dict:
    """Ingest pending output messages from a session into the target Knowledge Base.

    Serialization: acquires a per-(memory_base_id, session_id) asyncio.Lock before any
    DB or Chroma access.  Concurrent jobs for the same session wait up to
    _LOCK_WAIT_TIMEOUT_SECS; if the lock cannot be acquired in time, asyncio.TimeoutError
    is re-raised so execute_with_status records JobStatus.TIMED_OUT.

    Live cursor: after acquiring the lock, the current cursor_id is re-read from the DB.
    ``cursor_id`` (the argument) is the dispatch-time snapshot kept only for logging.

    Note: ``task_job_id`` (not ``job_id``) is used to avoid colliding with the
    ``job_id`` kwarg consumed by ``JobService.execute_with_status`` at the call site.

    Args:
        memory_base_id: ID of the MemoryBase configuration.
        session_id: Conversation/session identifier.
        flow_id: The flow whose outputs are being captured.
        kb_name: Target Knowledge Base directory name.
        kb_username: Username (filesystem path component for the KB).
        user_id: Owner UUID — passed to ``_build_embeddings`` for API-key resolution.
        embedding_provider: Embedding provider name (e.g. "OpenAI").
        embedding_model: Embedding model identifier.
        cursor_id: Dispatch-time snapshot of the last known cursor (for logging only).
                   The live cursor is re-read from the DB after lock acquisition.
        task_job_id: Job ID for cancellation checking.
        job_service: Service for checking cancellation.

    Returns:
        Dict with ingestion summary.

    Raises:
        asyncio.TimeoutError: If the session lock cannot be acquired within the timeout.
            execute_with_status catches this and records JobStatus.TIMED_OUT.
        Exception: Re-raises any other failure; cursor is NOT advanced on failure.
    """
    await logger.adebug(
        "Ingestion job started | memory_base=%s session=%s dispatch_cursor=%s job=%s",
        memory_base_id,
        session_id,
        cursor_id,
        task_job_id,
    )
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        msg = "Knowledge base root path is not configured"
        raise RuntimeError(msg)

    kb_path: Path = kb_root / kb_username / kb_name

    # ---- 0. Acquire per-session serialization lock ----
    # asyncio.TimeoutError is NOT caught here — it propagates to execute_with_status
    # which records JobStatus.TIMED_OUT. The lock is never held when TimeoutError fires,
    # so there is nothing to release.
    lock = _get_or_create_session_lock((memory_base_id, session_id))
    try:
        await asyncio.wait_for(lock.acquire(), timeout=_LOCK_WAIT_TIMEOUT_SECS)
    except asyncio.TimeoutError:
        await logger.awarning(
            "Ingestion lock wait timeout | memory_base=%s session=%s job=%s — re-raising for TIMED_OUT status.",
            memory_base_id,
            session_id,
            task_job_id,
        )
        raise

    try:
        # ---- 0b. Re-read live cursor inside the lock ----
        live_cursor_id = await _read_live_cursor(memory_base_id, session_id)
        await logger.adebug(
            "Ingestion lock acquired | memory_base=%s session=%s dispatch_cursor=%s live_cursor=%s job=%s",
            memory_base_id,
            session_id,
            cursor_id,
            live_cursor_id,
            task_job_id,
        )

        # ---- 1. Fetch pending output messages for this session ----
        messages = await _fetch_pending_messages(
            flow_id=flow_id,
            session_id=session_id,
            cursor_id=live_cursor_id,
        )
        if not messages:
            await logger.ainfo("MemoryBase %s / session %s: no pending messages, skipping.", memory_base_id, session_id)
            return {"message": "No pending messages", "ingested": 0}

        # ---- 2. Build documents from messages ----
        documents = _build_documents_from_messages(messages, session_id=session_id, flow_id=str(flow_id))

        if not documents:
            return {"message": "No non-empty messages to ingest", "ingested": 0}

        # ---- 3. Check cancellation before touching the vector store ----
        if await KBIngestionHelper.is_job_cancelled(job_service, task_job_id):
            return {"message": "Job cancelled before ingestion", "ingested": 0}

        # ---- 4. Open Chroma, write, then sync KB metadata — all before closing ----
        # user_stub carries only .id so that build_embeddings can resolve API keys.
        user_stub = types.SimpleNamespace(id=user_id)
        embeddings = await KBIngestionHelper.build_embeddings(embedding_provider, embedding_model, user_stub)

        client = KBStorageHelper.get_fresh_chroma_client(kb_path)
        written = 0
        try:
            chroma = Chroma(client=client, embedding_function=embeddings, collection_name=kb_name)

            written = await KBIngestionHelper.write_documents_to_chroma(
                documents=documents,
                chroma=chroma,
                task_job_id=task_job_id,
                job_service=job_service,
            )

            if written == len(documents):
                # Sync embedding_metadata.json while the collection is still open,
                # matching the pattern used by perform_ingestion.
                _sync_kb_metadata(kb_path=kb_path, chroma=chroma)
        finally:
            client = None
            chroma = None  # type: ignore[assignment]
            KBStorageHelper.release_chroma_resources(kb_path)

        if written < len(documents):
            # Job was cancelled mid-write; cursor must NOT advance.
            return {"message": "Job cancelled during ingestion", "ingested": 0}

        # ---- 5. Bulk-stamp ingestion metadata on every ingested message ----
        await _mark_messages_ingested(messages=messages, job_id=task_job_id, memory_base_id=memory_base_id)

        # ---- 6. Update cursor atomically ONLY after confirmed success ----
        last_message_id = messages[-1].id
        ingested_count = len(messages)
        await _advance_cursor(
            memory_base_id=memory_base_id,
            session_id=session_id,
            new_cursor_id=last_message_id,
            ingested_count=ingested_count,
            task_job_id=task_job_id,
        )

        await logger.ainfo(
            "Ingestion job finished | memory_base=%s session=%s job=%s ingested=%d new_cursor=%s",
            memory_base_id,
            session_id,
            task_job_id,
            ingested_count,
            last_message_id,
        )
        return {"message": "Success", "ingested": ingested_count}

    finally:
        lock.release()


async def _fetch_pending_messages(
    *,
    flow_id: uuid.UUID,
    session_id: str,
    cursor_id: uuid.UUID | None,
) -> list[MessageTable]:
    """Fetch all messages for this session that come after cursor_id.

    Ordering is (timestamp ASC, id ASC) — a deterministic, stable sort that
    handles same-timestamp ties correctly.  The cursor is a compound
    (cursor_ts, cursor_id) position: messages are included when
    ``timestamp > cursor_ts`` OR ``(timestamp == cursor_ts AND id > cursor_id)``.

    This prevents silent data loss when two messages share the same timestamp:
    any message with ts == cursor_ts but a UUID that sorts *after* the cursor id
    is correctly included in the next batch.  UUID ordering within a tie is
    arbitrary but consistent, so the partition is always correct.

    is_output filtering is intentionally omitted so the full conversation
    batch (user turns + model turns) is ingested into the KB.
    """
    from sqlalchemy import and_, or_

    async with session_scope() as db:
        stmt = (
            select(MessageTable)
            .where(MessageTable.flow_id == flow_id)
            .where(MessageTable.session_id == session_id)
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
    *,
    messages: list[MessageTable],
    job_id: uuid.UUID,
    memory_base_id: uuid.UUID,
) -> None:
    """Batch-insert ingestion records for all successfully ingested messages.

    Uses dialect-specific INSERT ... ON CONFLICT DO NOTHING for idempotency:
    if a job retries after Chroma write succeeds but before cursor advance,
    re-inserting the same rows is a safe no-op.
    Called only after a confirmed successful Chroma write.
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
    async with session_scope() as db:
        conn = await db.connection()
        if conn.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(MessageIngestionRecord).values(rows).on_conflict_do_nothing()
        else:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            stmt = sqlite_insert(MessageIngestionRecord).values(rows).on_conflict_do_nothing()
        await db.exec(stmt)  # type: ignore[call-overload]
        await db.commit()


def _extract_content_block_text(content_blocks: list) -> str:
    """Extract embeddable text from content blocks of type text, code, and json.

    Blocks of any other type (tool_use, error, media, etc.) are skipped.
    Each extracted piece is separated by a blank line so chunk boundaries
    remain readable in the vector store.
    """
    parts: list[str] = []
    for block in content_blocks:
        # content_blocks are stored as JSON; each block is a dict at runtime.
        contents: list = block.get("contents", []) if isinstance(block, dict) else []
        for entry in contents:
            if not isinstance(entry, dict):
                continue
            entry_type = entry.get("type")
            if entry_type == "text":
                fragment = (entry.get("text") or "").strip()
            elif entry_type == "code":
                lang = entry.get("language") or ""
                code = (entry.get("code") or "").strip()
                fragment = f"```{lang}\n{code}\n```" if code else ""
            elif entry_type == "json":
                data = entry.get("data")
                fragment = json.dumps(data, ensure_ascii=False) if data is not None else ""
            else:
                continue
            if fragment:
                parts.append(fragment)
    return "\n\n".join(parts)


def _build_documents_from_messages(
    messages: list[MessageTable],
    *,
    session_id: str,
    flow_id: str,
) -> list[Document]:
    """Convert MessageTable rows into LangChain Documents.

    Each message's embeddable text is the concatenation of msg.text and any
    content-block fragments whose type is text, code, or json.  Other block
    types (tool_use, error, media, …) are ignored.  Long combined texts are
    split by RecursiveCharacterTextSplitter before embedding.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_MESSAGE_CHUNK_SIZE,
        chunk_overlap=_MESSAGE_CHUNK_OVERLAP,
    )
    docs: list[Document] = []
    for msg in messages:
        parts: list[str] = []
        if msg.text and msg.text.strip():
            parts.append(msg.text.strip())
        cb_text = _extract_content_block_text(msg.content_blocks or [])
        if cb_text:
            parts.append(cb_text)

        text = "\n\n".join(parts)
        if not text:
            continue
        chunks = splitter.split_text(text)
        for i, chunk in enumerate(chunks):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "message_id": str(msg.id),
                        "session_id": session_id,
                        "flow_id": flow_id,
                        "sender": msg.sender,
                        "sender_name": msg.sender_name,
                        "timestamp": msg.timestamp.isoformat() if msg.timestamp else "",
                        "run_id": str(msg.run_id) if msg.run_id else "",
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "source": f"memory_base/{session_id}",
                    },
                )
            )
    return docs


def _sync_kb_metadata(*, kb_path: Path, chroma: Chroma) -> None:
    """Update embedding_metadata.json after a successful Memory Base ingestion.

    Mirrors the post-write metadata sync in ``KBIngestionHelper.perform_ingestion``:
    - Refreshes chunk / word / character counts from the live Chroma collection.
    - Updates on-disk size.
    - Stamps ``is_memory_base: true`` (required for Knowledge Retrieval filtering).
    - Sets ``source_types: ["memory"]`` to distinguish from file-based KBs.

    Called while the Chroma client is still open so that ``update_text_metrics``
    can query the collection directly without opening a second client.
    """
    try:
        metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
        KBAnalysisHelper.update_text_metrics(kb_path, metadata, chroma=chroma)
        metadata["size"] = KBStorageHelper.get_directory_size(kb_path)
        metadata["is_memory_base"] = True
        # Preserve any existing source_types but always include "memory"
        existing = set(metadata.get("source_types") or [])
        existing.add("memory")
        metadata["source_types"] = sorted(existing)
        (kb_path / "embedding_metadata.json").write_text(json.dumps(metadata, indent=2))
    except (OSError, json.JSONDecodeError, ValueError):
        # Metadata sync is best-effort; a failure here must not block the cursor advance.
        import logging

        logging.getLogger(__name__).warning("KB metadata sync failed for %s", kb_path, exc_info=True)


async def _advance_cursor(
    *,
    memory_base_id: uuid.UUID,
    session_id: str,
    new_cursor_id: uuid.UUID,
    ingested_count: int,
    task_job_id: uuid.UUID,
) -> None:
    """Atomically advance the cursor, update session stats, and stamp workflow run records.

    This is the FINAL step in ``ingest_memory_task``.  It must only be called
    after ``write_documents_to_chroma`` confirms all documents were successfully
    persisted.

    In addition to updating the message cursor and stats on MemoryBaseSession, this
    stamps all pending MemoryBaseWorkflowRun rows (ingestion_job_id IS NULL) for this
    session with ``task_job_id``.  This marks them as accounted-for so they are not
    re-counted toward the threshold on the next on_flow_output call.
    If ingestion fails and this function is never called, those rows stay NULL and are
    correctly re-counted on the next threshold check.
    """
    from sqlalchemy import update as sa_update

    async with session_scope() as db:
        stmt = (
            select(MemoryBaseSession)
            .where(MemoryBaseSession.memory_base_id == memory_base_id)
            .where(MemoryBaseSession.session_id == session_id)
        )
        result = await db.exec(stmt)
        mbs = result.first()
        if mbs is None:
            await logger.awarning(
                "MemoryBaseSession for (%s, %s) vanished before cursor update - skipping.",
                memory_base_id,
                session_id,
            )
            return

        mbs.cursor_id = new_cursor_id
        mbs.total_processed += ingested_count
        mbs.last_sync_at = datetime.now(timezone.utc)
        db.add(mbs)

        # Stamp all pending workflow run rows for this session as covered by this ingestion.
        await db.exec(  # type: ignore[call-overload]
            sa_update(MemoryBaseWorkflowRun)
            .where(MemoryBaseWorkflowRun.memory_base_id == memory_base_id)
            .where(MemoryBaseWorkflowRun.session_id == session_id)
            .where(MemoryBaseWorkflowRun.ingestion_job_id == None)  # noqa: E711
            .values(ingestion_job_id=task_job_id)
        )

        await db.commit()
