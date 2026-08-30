"""Document building and KB metadata sync helpers for Memory Base ingestion.

Extracted from task.py to separate "document shaping" from "ingestion orchestration".
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from lfx.log.logger import logger

from langflow.api.utils.kb_helpers import KBAnalysisHelper, chunk_text_for_ingestion

if TYPE_CHECKING:
    import uuid

    from lfx.base.knowledge_bases.backends.base import BaseVectorStoreBackend

    from langflow.services.database.models.message.model import MessageTable

# Chunk size for splitting long messages before embedding
MESSAGE_CHUNK_SIZE = 1000
MESSAGE_CHUNK_OVERLAP = 100


def extract_content_block_text(content_blocks: list) -> str:
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


def build_documents_from_messages(
    messages: list[MessageTable],
    *,
    session_id: str,
    flow_id: str,
    job_id: str = "",
    end_user_id: str | None = None,
) -> list[Document]:
    """Convert MessageTable rows into LangChain Documents.

    Each message's embeddable text is the concatenation of msg.text and any
    content-block fragments whose type is text, code, or json.  Other block
    types (tool_use, error, media, ...) are ignored.  Long combined texts are
    split by RecursiveCharacterTextSplitter before embedding.

    ``end_user_id`` (serving plane only; ``None`` off / editor / anonymous) is stamped
    as its own metadata field so cross-session recall can stay scoped to one end user in
    the shared service-account store — the session-id prefix is the only other end-user
    discriminator and it is dropped when ``filter_by_session`` is off.
    """
    docs: list[Document] = []
    for msg in messages:
        parts: list[str] = []
        if msg.text and msg.text.strip():
            parts.append(msg.text.strip())
        cb_text = extract_content_block_text(msg.content_blocks or [])
        if cb_text:
            parts.append(cb_text)

        text = "\n\n".join(parts)
        if not text:
            continue
        chunks = chunk_text_for_ingestion(
            text,
            chunk_size=MESSAGE_CHUNK_SIZE,
            chunk_overlap=MESSAGE_CHUNK_OVERLAP,
        )
        for i, chunk in enumerate(chunks):
            metadata = {
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
                "job_id": job_id,
            }
            # Only stamped when present, so off / editor / anonymous chunks carry no key
            # and the retrieval exact-match filter never falsely excludes them.
            if end_user_id:
                metadata["end_user_id"] = end_user_id
            docs.append(Document(page_content=chunk, metadata=metadata))
    return docs


def build_preprocessed_document(
    *,
    output_text: str,
    source_message_ids: list[str],
    session_id: str,
    flow_id: str,
    job_id: str,
    preproc_output_id: str,
    end_user_id: str | None = None,
) -> list[Document]:
    """Build LangChain Documents from a preprocessed (LLM-distilled) batch.

    Uses :func:`chunk_text_for_ingestion` so chunk size / overlap is identical
    across raw-message and preprocessed paths. Returns ``[]`` for empty output.

    Metadata mirrors :func:`build_documents_from_messages` and adds two keys:
      - ``preprocessed`` — boolean for query-side filtering / debug visibility.
      - ``preproc_output_id`` — pointer back to ``MemoryBasePreprocessingOutput``.

    ``end_user_id`` is stamped identically to the raw-message path (serving plane only;
    ``None`` off / editor / anonymous) so preprocessed chunks are scoped for
    cross-session recall too — otherwise they would leak across end users under the
    ``filter_by_session`` off toggle.
    """
    chunks = chunk_text_for_ingestion(
        output_text,
        chunk_size=MESSAGE_CHUNK_SIZE,
        chunk_overlap=MESSAGE_CHUNK_OVERLAP,
    )
    if not chunks:
        return []
    docs: list[Document] = []
    for i, chunk in enumerate(chunks):
        metadata = {
            "session_id": session_id,
            "flow_id": flow_id,
            "sender": "Machine",
            "sender_name": "Preprocessor",
            "timestamp": "",
            "run_id": "",
            "chunk_index": i,
            "total_chunks": len(chunks),
            "source": f"memory_base/{session_id}",
            "job_id": job_id,
            "preprocessed": True,
            "preproc_output_id": preproc_output_id,
            "source_message_ids": ",".join(source_message_ids),
        }
        if end_user_id:
            metadata["end_user_id"] = end_user_id
        docs.append(Document(page_content=chunk, metadata=metadata))
    return docs


async def sync_kb_stats_to_record(
    *,
    user_id: uuid.UUID,
    kb_name: str,
    backend: BaseVectorStoreBackend,
) -> None:
    """Refresh the ``knowledge_base`` row's cached counts after a Memory Base write.

    Memory Bases are DB-driven: their chunk / word / character / size stats live
    on the row, not an on-disk ``embedding_metadata.json`` sidecar, so a replica
    with no local KB directory still reports accurate numbers. Counts come from the
    backend's ``count`` / ``iter_documents`` / ``storage_size_bytes`` abstraction,
    so every vector store (Chroma / Chroma Cloud / OpenSearch) is covered.

    Best-effort: a stats-refresh failure must never fail an ingestion whose writes
    already succeeded. Silently returns when no row exists (nothing to update).
    """
    from langflow.api.utils import knowledge_base_service

    try:
        record = await knowledge_base_service.get_by_user_and_name(user_id, kb_name)
        if record is None:
            return
        metrics: dict = {}
        await KBAnalysisHelper.update_text_metrics_via_backend(metrics, backend)
        try:
            size_bytes = await backend.storage_size_bytes()
        except Exception as exc:  # noqa: BLE001 — size is cosmetic, never fail ingestion for it
            await logger.adebug(f"Backend storage_size_bytes() failed during stats sync: {exc}")
            size_bytes = 0
        # Preserve any existing source_types but always keep the "memory" marker.
        source_types = sorted(set(record.source_types or []) | {"memory"})
        await knowledge_base_service.update_stats(
            record.id,
            chunks=metrics.get("chunks", 0),
            words=metrics.get("words", 0),
            characters=metrics.get("characters", 0),
            size_bytes=size_bytes,
            source_types=source_types,
        )
    except Exception:  # noqa: BLE001 — stats are best-effort; never fail a committed ingestion
        await logger.awarning("KB stats sync to row failed for kb_name=%s", kb_name, exc_info=True)
