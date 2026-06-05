"""KB path resolution and username helpers for MemoryBase.

Extracted from MemoryBaseService to keep single-responsibility per file.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.base.vectorstores.chroma_security import chroma_client_create_collection_kwargs
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBStorageHelper
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from pathlib import Path

    from sqlmodel.ext.asyncio.session import AsyncSession


def validate_kb_path(kb_root: Path, kb_path: Path) -> None:
    """Assert that kb_path is contained within kb_root (path traversal guard).

    Prevents crafted usernames with '..' segments from escaping the KB root directory.
    Follows the same pattern as services/storage/local.py:save_file.
    """
    kb_root_resolved = kb_root.resolve()
    kb_path_resolved = kb_path.resolve()
    if not kb_path_resolved.is_relative_to(kb_root_resolved):
        msg = "KB path escapes root directory"
        raise ValueError(msg)


def hash_session_id(session_id: str) -> str:
    """Return a truncated SHA-256 hash for safe logging of session IDs."""
    return hashlib.sha256(session_id.encode()).hexdigest()[:12]


def sanitize_kb_name(name: str) -> str:
    """Lowercase, replace spaces/hyphens with underscores, strip non-alphanum."""
    sanitized = name.strip().lower()
    sanitized = re.sub(r"[\s\-]+", "_", sanitized)
    sanitized = re.sub(r"[^\w]", "", sanitized)
    return sanitized or "memory"


async def resolve_kb_username(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Look up the username for a user_id within an existing DB session."""
    from langflow.services.database.models.user.model import User

    stmt = select(User.username).where(User.id == user_id)
    result = await db.exec(stmt)
    username = result.first()
    if not username:
        msg = f"User {user_id} not found"
        raise ValueError(msg)
    return username


async def resolve_kb_username_by_user_id(user_id: uuid.UUID) -> str:
    """Look up the username for a user_id using a fresh DB session."""
    async with session_scope() as db:
        return await resolve_kb_username(db, user_id)


def resolve_embedding(kb_name: str, kb_username: str) -> tuple[str, str]:
    """Read embedding provider/model from KB metadata.json, with sane defaults."""
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        return "OpenAI", "text-embedding-3-small"
    kb_path: Path = kb_root / kb_username / kb_name
    metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
    provider = metadata.get("embedding_provider") or "OpenAI"
    model = metadata.get("embedding_model") or "text-embedding-3-small"
    return provider, model


async def initialize_kb(
    *,
    kb_name: str,
    kb_username: str,
    embedding_provider: str,
    embedding_model: str,
) -> None:
    """Create KB directory, initialize Chroma, and write embedding_metadata.json.

    Mirrors the logic in knowledge_bases.py:create_knowledge_base so Memory Base
    KBs are immediately visible with the correct metadata (including is_memory_base: true).
    """
    import chromadb

    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        await logger.awarning("KB root path not configured — Memory Base KB will not be initialized on disk.")
        return

    kb_path: Path = kb_root / kb_username / kb_name
    validate_kb_path(kb_root, kb_path)
    await asyncio.to_thread(kb_path.mkdir, parents=True, exist_ok=True)

    # Initialize Chroma collection so the directory is non-empty and readable
    try:
        client = KBStorageHelper.get_fresh_chroma_client(kb_path)
        client.create_collection(name=kb_name, **chroma_client_create_collection_kwargs())
    except (OSError, ValueError, chromadb.errors.ChromaError) as exc:
        await logger.awarning("Initial Chroma setup for %s failed: %s", kb_name, exc)
    finally:
        client = None  # type: ignore[assignment]
        KBStorageHelper.release_chroma_resources(kb_path)

    embedding_metadata = {
        "id": str(uuid.uuid4()),
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "is_memory_base": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chunks": 0,
        "words": 0,
        "characters": 0,
        "avg_chunk_size": 0.0,
        "size": 0,
        "source_types": ["memory"],
    }
    await asyncio.to_thread(
        (kb_path / "embedding_metadata.json").write_text,
        json.dumps(embedding_metadata, indent=2),
    )


async def delete_kb(*, kb_name: str, kb_username: str) -> None:
    """Remove the KB directory from disk. Logs on failure, does not raise."""
    if not kb_name:
        return
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        return
    kb_path = kb_root / kb_username / kb_name
    validate_kb_path(kb_root, kb_path)
    try:
        await asyncio.to_thread(KBStorageHelper.delete_storage, kb_path, kb_name)
    except (OSError, ValueError):
        await logger.awarning("Could not delete KB '%s' from disk after Memory Base deletion.", kb_name, exc_info=True)
