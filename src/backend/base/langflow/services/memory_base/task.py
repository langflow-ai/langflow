"""Background task for Memory Base ingestion.

Design principles enforced here:
- Cursor atomicity: cursor_id is NEVER updated before ingestion confirms success.
- Retry safety: If a job fails, cursor_id remains at the last known good position.
- Immutable args: All parameters (including cursor_id) are captured at task creation time.

The actual Chroma write logic is shared with KB file ingestion via
``KBIngestionHelper.write_documents_to_chroma`` — no duplicate batching/retry code here.
"""

from __future__ import annotations

import json
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBIngestionHelper, KBStorageHelper
from langflow.services.database.models.memory_base.model import MemoryBaseSession
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from langflow.services.jobs.service import JobService

# Chunk size for splitting long messages before embedding
_MESSAGE_CHUNK_SIZE = 1000
_MESSAGE_CHUNK_OVERLAP = 100


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

    All arguments are immutable and captured at task-dispatch time.
    The cursor is updated ONLY after successful ingestion.

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
        cursor_id: Last successfully ingested message ID (exclusive lower bound).
        task_job_id: Job ID for cancellation checking.
        job_service: Service for checking cancellation.

    Returns:
        Dict with ingestion summary.

    Raises:
        Exception: Re-raises any failure; cursor is NOT advanced on failure.
    """
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        msg = "Knowledge base root path is not configured"
        raise RuntimeError(msg)

    kb_path: Path = kb_root / kb_username / kb_name

    # ---- 1. Fetch pending output messages for this session ----
    messages = await _fetch_pending_messages(
        flow_id=flow_id,
        session_id=session_id,
        cursor_id=cursor_id,
    )

    if not messages:
        await logger.ainfo("MemoryBase %s / session %s: no pending messages, skipping.", memory_base_id, session_id)
        return {"message": "No pending messages", "ingested": 0}

    # ---- 2. Build documents from messages ----
    documents = _build_documents_from_messages(messages, session_id=session_id, flow_id=str(flow_id))

    if not documents:
        return {"message": "No non-empty messages to ingest", "ingested": 0}

    # ---- 3. Check cancellation before touching the vector store ----
    if await KBIngestionHelper._is_job_cancelled(job_service, task_job_id):
        return {"message": "Job cancelled before ingestion", "ingested": 0}

    # ---- 4. Open Chroma, write, then sync KB metadata — all before closing ----
    # user_stub carries only .id so that _build_embeddings can resolve API keys.
    user_stub = types.SimpleNamespace(id=user_id)
    embeddings = await KBIngestionHelper._build_embeddings(embedding_provider, embedding_model, user_stub)

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

    # ---- 5. Update cursor atomically ONLY after confirmed success ----
    last_message_id = messages[-1].id
    ingested_count = len(messages)
    await _advance_cursor(
        memory_base_id=memory_base_id,
        session_id=session_id,
        new_cursor_id=last_message_id,
        ingested_count=ingested_count,
    )

    await logger.ainfo(
        "MemoryBase %s / session %s: ingested %d messages. New cursor: %s",
        memory_base_id,
        session_id,
        ingested_count,
        last_message_id,
    )
    return {"message": "Success", "ingested": ingested_count}


async def _fetch_pending_messages(
    *,
    flow_id: uuid.UUID,
    session_id: str,
    cursor_id: uuid.UUID | None,
) -> list[MessageTable]:
    """Fetch all messages for this session that come after cursor_id.

    is_output filtering is intentionally omitted so the full conversation
    batch (user turns + model turns) is ingested into the KB.
    """
    async with session_scope() as db:
        stmt = (
            select(MessageTable)
            .where(MessageTable.flow_id == flow_id)
            .where(MessageTable.session_id == session_id)
            .order_by(col(MessageTable.timestamp).asc())
        )
        if cursor_id is not None:
            cursor_stmt = select(MessageTable.timestamp).where(MessageTable.id == cursor_id)
            result = await db.exec(cursor_stmt)
            cursor_ts = result.first()
            if cursor_ts:
                stmt = stmt.where(col(MessageTable.timestamp) > cursor_ts)

        result = await db.exec(stmt)
        return list(result.all())


def _build_documents_from_messages(
    messages: list[MessageTable],
    *,
    session_id: str,
    flow_id: str,
) -> list[Document]:
    """Convert MessageTable rows into LangChain Documents.

    Long messages are split by RecursiveCharacterTextSplitter to keep chunk
    sizes manageable for embedding.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_MESSAGE_CHUNK_SIZE,
        chunk_overlap=_MESSAGE_CHUNK_OVERLAP,
    )
    docs: list[Document] = []
    for msg in messages:
        text = (msg.text or "").strip()
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
    except Exception:
        # Metadata sync is best-effort; a failure here must not block the cursor advance.
        import logging

        logging.getLogger(__name__).warning("KB metadata sync failed for %s", kb_path, exc_info=True)


async def _advance_cursor(
    *,
    memory_base_id: uuid.UUID,
    session_id: str,
    new_cursor_id: uuid.UUID,
    ingested_count: int,
) -> None:
    """Atomically advance the cursor and update stats for a MemoryBaseSession.

    This is the FINAL step in ``ingest_memory_task``.  It must only be called
    after ``write_documents_to_chroma`` confirms all documents were successfully
    persisted.
    """
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
                "MemoryBaseSession for (%s, %s) vanished before cursor update – skipping.",
                memory_base_id,
                session_id,
            )
            return

        mbs.cursor_id = new_cursor_id
        mbs.total_processed += ingested_count
        mbs.last_sync_at = datetime.now(timezone.utc)
        db.add(mbs)
        await db.commit()
