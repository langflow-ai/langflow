"""Document building and KB metadata sync helpers for Memory Base ingestion.

Extracted from task.py to separate "document shaping" from "ingestion orchestration".
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.log.logger import logger

from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBStorageHelper

if TYPE_CHECKING:
    from pathlib import Path

    from langchain_chroma import Chroma

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
) -> list[Document]:
    """Convert MessageTable rows into LangChain Documents.

    Each message's embeddable text is the concatenation of msg.text and any
    content-block fragments whose type is text, code, or json.  Other block
    types (tool_use, error, media, ...) are ignored.  Long combined texts are
    split by RecursiveCharacterTextSplitter before embedding.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MESSAGE_CHUNK_SIZE,
        chunk_overlap=MESSAGE_CHUNK_OVERLAP,
    )
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
                        "job_id": job_id,
                    },
                )
            )
    return docs


def sync_kb_metadata(*, kb_path: Path, chroma: Chroma) -> None:
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
        # Note: this runs inside asyncio.to_thread so we use sync logging here.
        # The lfx logger's sync .warning() method goes through the same structured pipeline.
        logger.warning("KB metadata sync failed for kb_path=%s", kb_path, exc_info=True)
