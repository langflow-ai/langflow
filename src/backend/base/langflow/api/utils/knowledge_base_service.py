"""CRUD + backfill helpers for ``knowledge_base`` rows.

Two responsibilities:

1. **Dual-write** helpers the existing KB code paths can adopt without
   a big-bang refactor — every ``create_record`` / ``update_stats``
   call is paired with continued JSON-file writes in ``kb_helpers`` so
   older service versions still see an intact filesystem view.

2. **DB-first read** helper that consolidates metadata from either the
   row or the on-disk JSON, whichever is populated. New KBs live only
   in the DB after Phase 1.5; older KBs continue to work because the
   startup reconciliation upserts rows for any directory that lacks one.

Kept small and procedural on purpose — no repository class because
the CRUD surface is tiny (create, upsert, update counters, update
status, delete, get_by_*_, list_by_user, backfill_from_disk) and
Phase 2's new endpoints will add their own query methods alongside.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord, KnowledgeBaseStatus
from langflow.services.deps import session_scope
from langflow.services.memory_base.embedding_helpers import infer_embedding_provider


class _UnsetType:
    """Sentinel for optional fields where ``None`` is a valid value."""


_UNSET = _UnsetType()


def get_embedding_provider(model_selection: Any) -> str:
    """Extract the provider name from a ``model_selection`` payload.

    ``model_selection`` is the canonical source of truth for embedding
    config on a KB; this helper centralizes the "what provider is this
    KB on" lookup so the answer doesn't drift between callers.

    Accepts the persisted dict shape (``{"name": ..., "provider": ...}``),
    the list-wrapped shape used by some unified-models entry points, or
    ``None``. Returns ``"Unknown"`` when nothing usable is present so
    list-style API responses can render a stable column.
    """
    selection = _coerce_model_dict(model_selection)
    if not selection:
        return "Unknown"
    provider = selection.get("provider")
    return str(provider).strip() if provider else "Unknown"


def get_embedding_model(model_selection: Any) -> str:
    """Extract the model name from a ``model_selection`` payload.

    Counterpart to :func:`get_embedding_provider`. Returns ``""`` (rather
    than ``"Unknown"``) on missing input — call sites distinguish
    "model unknown" (display-only) from "model missing" (don't try to
    instantiate embeddings).
    """
    selection = _coerce_model_dict(model_selection)
    if not selection:
        return ""
    name = selection.get("name")
    return str(name).strip() if name else ""


def _coerce_model_dict(model_selection: Any) -> dict[str, Any] | None:
    """Coerce ``model_selection`` to the canonical single-dict form."""
    if model_selection is None:
        return None
    if isinstance(model_selection, list):
        return model_selection[0] if model_selection else None
    if isinstance(model_selection, dict):
        return model_selection
    return None


async def create_record(
    *,
    user_id: UUID,
    name: str,
    model_selection: dict[str, Any] | list[dict[str, Any]] | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separator: str | None = None,
    column_config: list[dict[str, Any]] | None = None,
    backend_type: str = "chroma",
    backend_config: dict[str, Any] | None = None,
    chunks: int = 0,
    words: int = 0,
    characters: int = 0,
    size_bytes: int = 0,
    source_types: list[str] | None = None,
    record_id: UUID | None = None,
) -> KnowledgeBaseRecord:
    """Insert a new KB record. Caller should already hold the name lock.

    ``model_selection`` is the single source of truth for embedding
    config — the legacy ``embedding_provider`` / ``embedding_model``
    flat columns were dropped in favor of the
    :func:`get_embedding_provider` / :func:`get_embedding_model` helpers
    that read from ``model_selection``. Callers that previously passed
    those two params now just supply ``model_selection``.
    """
    normalized_selection = _normalize_model_selection(model_selection)
    record = KnowledgeBaseRecord(
        id=record_id or uuid4(),
        name=name,
        user_id=user_id,
        model_selection=normalized_selection,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separator=separator,
        column_config=column_config or [],
        backend_type=backend_type,
        backend_config=backend_config or {},
        chunks=chunks,
        words=words,
        characters=characters,
        size_bytes=size_bytes,
        source_types=sorted(set(source_types or [])),
        status=KnowledgeBaseStatus.READY.value,
    )
    async with session_scope() as session:
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return record


async def get_by_user_and_name(user_id: UUID, name: str) -> KnowledgeBaseRecord | None:
    async with session_scope() as session:
        stmt = select(KnowledgeBaseRecord).where(
            KnowledgeBaseRecord.user_id == user_id,
            KnowledgeBaseRecord.name == name,
        )
        result = await session.exec(stmt)
        return result.first()


async def get_by_id(record_id: UUID) -> KnowledgeBaseRecord | None:
    async with session_scope() as session:
        return await session.get(KnowledgeBaseRecord, record_id)


async def list_by_name(name: str) -> list[KnowledgeBaseRecord]:
    """Return every KB record with the given ``name`` across all users.

    Cross-user share resolution: ``(user_id, name)`` is the unique key per
    user, but the name itself can collide across users. Callers that need
    to find a non-owned KB referenced by a share grant scan name matches and
    let the enforcer pick the one the actor can reach.
    """
    async with session_scope() as session:
        stmt = select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.name == name)
        result = await session.exec(stmt)
        return list(result.all())


async def list_by_user(user_id: UUID) -> list[KnowledgeBaseRecord]:
    """Return all KBs for ``user_id`` (newest first)."""
    async with session_scope() as session:
        stmt = (
            select(KnowledgeBaseRecord)
            .where(KnowledgeBaseRecord.user_id == user_id)
            .order_by(KnowledgeBaseRecord.created_at.desc())  # type: ignore[attr-defined]
        )
        result = await session.exec(stmt)
        return list(result.all())


async def backfill_all_users_from_disk(*, kb_root: Path | None = None) -> int:
    """Backfill missing KB rows for every existing user.

    Runs during application startup so list/detail endpoints can stay
    read-only. Returns the total number of inserted rows across all
    users and never raises for per-user failures.
    """
    from langflow.api.utils.kb_helpers import KBStorageHelper
    from langflow.services.database.models.user.model import User

    effective_root = kb_root or KBStorageHelper.get_root_path()
    if not effective_root.exists():
        return 0

    async with session_scope() as session:
        users = list((await session.exec(select(User))).all())

    inserted = 0
    for user in users:
        kb_user_root = effective_root / user.username
        if not kb_user_root.exists():
            continue
        try:
            inserted += await backfill_from_disk(user_id=user.id, kb_user_root=kb_user_root)
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(
                "knowledge-base startup reconciliation failed for user %s: %s",
                user.username,
                exc,
            )

    return inserted


async def update_stats(
    record_id: UUID,
    *,
    chunks: int | None = None,
    words: int | None = None,
    characters: int | None = None,
    size_bytes: int | None = None,
    source_types: list[str] | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    separator: str | None | _UnsetType = _UNSET,
) -> None:
    """Refresh the cached aggregates + chunker settings after an ingestion run.

    Silently returns if the row is missing — the row may have been
    deleted between the ingestion start and the finalize call; we
    don't want that to fail the run.
    """
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record_id)
        if row is None:
            await logger.awarning("knowledge_base row %s missing on update_stats; skipping", record_id)
            return
        if chunks is not None:
            row.chunks = chunks
        if words is not None:
            row.words = words
        if characters is not None:
            row.characters = characters
        if size_bytes is not None:
            row.size_bytes = size_bytes
        if source_types is not None:
            row.source_types = sorted(set(source_types))
        if chunk_size is not None:
            row.chunk_size = chunk_size
        if chunk_overlap is not None:
            row.chunk_overlap = chunk_overlap
        if not isinstance(separator, _UnsetType):
            row.separator = separator
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.commit()


async def update_status(
    record_id: UUID,
    *,
    status: KnowledgeBaseStatus,
    failure_reason: str | None = None,
) -> None:
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record_id)
        if row is None:
            return
        row.status = status.value
        row.failure_reason = failure_reason
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.commit()


async def update_column_config(
    record_id: UUID,
    column_config: list[dict[str, Any]],
) -> None:
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record_id)
        if row is None:
            return
        row.column_config = column_config
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.commit()


async def delete_record(record_id: UUID) -> None:
    """Remove the KB row. Caller is responsible for filesystem cleanup."""
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record_id)
        if row is None:
            return
        await session.delete(row)
        await session.commit()


async def delete_by_user_and_name(user_id: UUID, name: str) -> None:
    record = await get_by_user_and_name(user_id, name)
    if record is not None:
        await delete_record(record.id)


async def read_metadata(
    *,
    user_id: UUID,
    name: str,
    kb_path: Path,
) -> dict[str, Any]:
    """Return KB metadata, preferring the DB row over the JSON file.

    Older KBs that pre-date Phase 1.5 (or were created by an older
    service version during the rollout) may only exist on disk —
    ``load_metadata_from_disk`` is the fallback. When both sources
    exist, the DB wins: it's the authoritative copy going forward.
    """
    record = await get_by_user_and_name(user_id, name)
    if record is not None:
        return record_to_metadata_dict(record)

    return load_metadata_from_disk(kb_path)


def record_to_metadata_dict(record: KnowledgeBaseRecord) -> dict[str, Any]:
    """Serialize a row into the legacy JSON-file shape.

    Matches the keys ``KBAnalysisHelper.get_metadata`` and the API
    routes expect so a DB-first migration doesn't need a parallel
    consumer refactor.
    """
    status = record.status
    if status == KnowledgeBaseStatus.READY.value and record.chunks <= 0:
        status = "empty"

    return {
        "id": str(record.id),
        "name": record.name,
        # Flat fields are derived views over ``model_selection`` — kept
        # in the response shape for API back-compat (the frontend reads
        # ``embedding_provider`` / ``embedding_model`` as flat keys),
        # but the canonical source of truth is ``model_selection``.
        "embedding_provider": get_embedding_provider(record.model_selection),
        "embedding_model": get_embedding_model(record.model_selection),
        "model_selection": record.model_selection or None,
        "chunk_size": record.chunk_size,
        "chunk_overlap": record.chunk_overlap,
        "separator": record.separator,
        "column_config": record.column_config,
        "backend_type": record.backend_type,
        "backend_config": record.backend_config,
        "chunks": record.chunks,
        "words": record.words,
        "characters": record.characters,
        "size": record.size_bytes,
        "source_types": record.source_types,
        "status": status,
        "failure_reason": record.failure_reason,
        "avg_chunk_size": round(record.characters / record.chunks, 1) if record.chunks > 0 else 0.0,
    }


def load_metadata_from_disk(kb_path: Path) -> dict[str, Any]:
    """Read ``embedding_metadata.json`` from ``kb_path``.

    Extracted so the backfill + fallback paths share a single parser.
    Returns an empty dict when the file is missing or malformed —
    callers treat that as "no DB row yet" and either backfill or emit
    a 404.
    """
    metadata_file = kb_path / "embedding_metadata.json"
    if not metadata_file.exists():
        return {}
    try:
        return json.loads(metadata_file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Failed to read KB metadata file %s: %s", metadata_file, exc)
        return {}


async def backfill_from_disk(
    *,
    user_id: UUID,
    kb_user_root: Path,
) -> int:
    """Create missing ``knowledge_base`` rows for existing KB directories.

    Called on first boot after the Phase 1.5 migration lands so every
    pre-existing KB gains a row. Also serves as an idempotent
    fallback: if a user drops an exported KB directory on disk, this
    upserts the corresponding row on next access.

    Returns the number of rows inserted. Never raises — failures are
    logged and skipped so one malformed KB directory doesn't block the
    rest.
    """
    if not kb_user_root.exists():
        return 0

    from langflow.api.utils.kb_helpers import KBStorageHelper

    inserted = 0
    for kb_dir in kb_user_root.iterdir():
        if not kb_dir.is_dir() or kb_dir.name.startswith("."):
            continue

        # Skip directories carrying the ``.kb_deleted`` sentinel: their DB
        # row was intentionally deleted but the bytes could not be removed
        # (typically a Windows Chroma SQLite lock).  Without this check the
        # next startup re-inserts the row and the deleted KB reappears.
        if KBStorageHelper.is_kb_dir_deleted(kb_dir):
            continue

        name = kb_dir.name
        existing = await get_by_user_and_name(user_id, name)
        if existing is not None:
            continue

        metadata = load_metadata_from_disk(kb_dir)
        if not metadata:
            # Unreadable metadata: skip. A subsequent ingestion will
            # rewrite the file and the next backfill will pick it up.
            continue

        try:
            from langflow.api.utils.kb_helpers import KBAnalysisHelper

            metadata = KBAnalysisHelper.get_metadata(kb_dir, fast=False) or metadata
            model_selection = _normalize_model_selection(metadata.get("model_selection"))
            record_id = _coerce_uuid(metadata.get("id")) or uuid4()
            # ``backend_type``/``backend_config`` are persisted by
            # ``create_knowledge_base`` into ``embedding_metadata.json``
            # precisely so a later backfill can reconstruct the correct
            # routing. Fall back to "chroma" only when the file
            # predates the multi-backend change (legacy KBs).
            backend_type = str(metadata.get("backend_type") or "chroma")
            backend_config_raw = metadata.get("backend_config") or {}
            backend_config = backend_config_raw if isinstance(backend_config_raw, dict) else {}
            # Synthesise ``model_selection`` from legacy flat fields
            # when the on-disk metadata predates the unified-models
            # work. Reuse :func:`infer_embedding_provider` (#12417) so
            # backfilled rows get a non-"Unknown" provider whenever the
            # model name is recognizable
            # (e.g. ``text-embedding-3-small`` → ``OpenAI``).
            normalized_selection = _normalize_model_selection(model_selection)
            if not normalized_selection:
                embedding_model_raw = str(metadata.get("embedding_model") or "")
                provider_raw = str(metadata.get("embedding_provider") or "Unknown")
                if provider_raw == "Unknown" and embedding_model_raw:
                    provider_raw = infer_embedding_provider(embedding_model_raw)
                if embedding_model_raw or provider_raw != "Unknown":
                    normalized_selection = {
                        "name": embedding_model_raw,
                        "provider": provider_raw,
                    }

            await create_record(
                user_id=user_id,
                name=name,
                model_selection=normalized_selection,
                chunk_size=int(metadata.get("chunk_size") or 1000),
                chunk_overlap=int(metadata.get("chunk_overlap") or 200),
                separator=metadata.get("separator"),
                column_config=metadata.get("column_config") or [],
                backend_type=backend_type,
                backend_config=backend_config,
                chunks=_coerce_int(metadata.get("chunks"), default=0),
                words=_coerce_int(metadata.get("words"), default=0),
                characters=_coerce_int(metadata.get("characters"), default=0),
                size_bytes=_coerce_int(metadata.get("size_bytes", metadata.get("size")), default=0),
                source_types=_coerce_source_types(metadata.get("source_types")),
                record_id=record_id,
            )
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            await logger.aerror("backfill: failed to upsert KB %s/%s: %s", user_id, name, exc)

    return inserted


def _normalize_model_selection(raw) -> dict[str, Any]:
    """Collapse a model_selection to its canonical single-dict form."""
    if raw is None:
        return {}
    if isinstance(raw, list):
        return raw[0] if raw else {}
    if isinstance(raw, dict):
        return raw
    return {}


def _coerce_uuid(value) -> UUID | None:
    """Safely coerce a mixed-type value to ``UUID`` or ``None``."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _coerce_int(value, *, default: int) -> int:
    """Safely coerce metadata counters from legacy JSON into non-negative ints."""
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return max(coerced, 0)


def _coerce_source_types(value) -> list[str]:
    """Normalize legacy source type metadata into a stable list of strings."""
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if str(item).strip()})
