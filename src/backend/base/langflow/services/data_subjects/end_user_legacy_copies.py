"""End-user erase: pre-upgrade copies of a Memory Base that still hold the person's chunks.

The automatic Chroma-to-SQLite upgrade retains the original directory and a snapshot, and deleting
the base keeps them. ``memory_vectors`` reaches only the live store, so this step walks the upgrade
ledger, one run per call, and removes each retained copy that mentions the person. A copy that may
still be the only data of a store that has not finished upgrading is left alone, and
``memory_vectors`` holds the request open for that store.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.knowledge_base_storage.retained import (
    copy_mentions,
    file_mentions,
    remove_copy,
    remove_file,
    retained_copies,
    run_directory,
)
from langflow.services.knowledge_base_storage.runtime import (
    StorageUnavailableError,
    shared_lock,
    storage_root,
    storage_unavailable_message,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext

CURSOR_KEY = "memory_legacy_copies_after"
DELETING_STATE = "deleting"
DELETED_STATE = "deleted"


async def _next_run(session: AsyncSession, ctx: EraseContext) -> KnowledgeBaseStorageMigration | None:
    stmt = (
        select(KnowledgeBaseStorageMigration)
        .where(col(KnowledgeBaseStorageMigration.source_identity).is_not(None))
        .order_by(col(KnowledgeBaseStorageMigration.id))
        .limit(1)
    )
    if after := ctx.cursor.get(CURSOR_KEY):
        stmt = stmt.where(col(KnowledgeBaseStorageMigration.id) > UUID(after))
    return (await session.exec(stmt)).first()


def _unattributed(record: KnowledgeBaseRecord | None) -> bool:
    """A base that is gone or going has no Memory Base row left to attribute its copies to."""
    return record is None or record.storage_state in (DELETING_STATE, DELETED_STATE)


def _superseded(record: KnowledgeBaseRecord | None, run: KnowledgeBaseStorageMigration) -> bool:
    """The copy no longer backs live data: its base is deleted, or serves a published newer generation."""
    if record is None or record.storage_state == DELETED_STATE:
        return True
    return (
        record.backend_type != "chroma"
        and record.storage_state == "ready"
        and record.storage_generation >= run.target_generation
    )


async def _in_scope(session: AsyncSession, ctx: EraseContext, record: KnowledgeBaseRecord | None) -> bool:
    if record is not None:
        stmt = select(MemoryBase.id).where(MemoryBase.user_id == record.user_id, MemoryBase.kb_name == record.name)
        if ctx.scope_flow_ids:
            stmt = stmt.where(col(MemoryBase.flow_id).in_(ctx.scope_flow_ids))
        if (await session.exec(stmt.limit(1))).first() is not None:
            return True
    # Without a flow to attribute the copies to, only an unscoped erase reaches them.
    return _unattributed(record) and not ctx.scope_flow_ids


def _mentioning(root: Path, run: KnowledgeBaseStorageMigration, end_user_id: str) -> tuple[list[Path], list[Path]]:
    """The retained copies and leftover export of one run that may hold the person's chunks."""
    if run.source_identity is None:
        return [], []
    copies = retained_copies(root, kb_id=run.kb_id, run_id=run.id, source_identity=run.source_identity)
    export = run_directory(root, kb_id=run.kb_id, run_id=run.id) / "export.jsonl"
    return (
        [copy for copy in copies if copy.is_dir() and copy_mentions(copy, end_user_id)],
        [export] if export.is_file() and file_mentions(export, end_user_id) else [],
    )


def _remove(root: Path, copies: list[Path], files: list[Path]) -> None:
    for copy in copies:
        remove_copy(copy, root)
    for path in files:
        remove_file(path, root)


async def _purge(run: KnowledgeBaseStorageMigration, end_user_id: str) -> None:
    # The store's lease excludes a migration or deletion that would read or retire these copies.
    async with shared_lock(run.kb_id):
        async with session_scope() as session:
            record = await session.get(KnowledgeBaseRecord, run.kb_id)
        superseded = _superseded(record, run)
        if not superseded and (record is None or record.storage_state != DELETING_STATE):
            return
        root = storage_root()
        copies, files = await asyncio.to_thread(_mentioning, root, run, end_user_id)
        if not (copies or files):
            return
        if not superseded:
            # A failed deletion keeps the copies. Retry once it finishes, like ``memory_vectors`` does.
            raise StorageUnavailableError(storage_unavailable_message(DELETING_STATE))
        await asyncio.to_thread(_remove, root, copies, files)


async def erase_retained_memory_copies(session: AsyncSession, ctx: EraseContext) -> int:
    if ctx.end_user is None or not get_settings_service().settings.knowledge_bases_dir:
        return 0
    run = await _next_run(session, ctx)
    if run is None:
        return 0
    record = await session.get(KnowledgeBaseRecord, run.kb_id)
    if await _in_scope(session, ctx, record):
        try:
            await _purge(run, ctx.end_user.raw_id)
        except Exception as exc:
            await logger.awarning(
                "op=data_subject_erase retained copies of kb_id=%s run_id=%s not erased: %s",
                run.kb_id,
                run.id,
                type(exc).__name__,
            )
            raise
    ctx.cursor[CURSOR_KEY] = str(run.id)
    return 1
