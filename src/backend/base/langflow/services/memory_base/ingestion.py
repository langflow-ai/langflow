"""Ingestion orchestration for MemoryBase — auto-capture, regeneration, and mismatch detection.

Extracted from MemoryBaseService to keep single-responsibility per file.
The MemoryBaseService delegates to these functions for all ingestion-related work.
"""

from __future__ import annotations

import asyncio
import types
import uuid
from typing import TYPE_CHECKING

import chromadb.errors
from langchain_chroma import Chroma
from lfx.base.vectorstores.chroma_security import chroma_langchain_collection_kwargs
from lfx.log.logger import logger
from sqlmodel import col, func, select

from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBIngestionHelper, KBStorageHelper
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBaseSession,
    MemoryBaseWorkflowRun,
)
from langflow.services.deps import get_job_service, get_task_service, session_scope
from langflow.services.jobs import DuplicateJobError
from langflow.services.memory_base.kb_path_helpers import (
    hash_session_id,
    resolve_embedding,
    resolve_kb_username,
    resolve_kb_username_by_user_id,
    validate_kb_path,
)
from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def trigger_ingestion(
    memory_base_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: str,
    *,
    get_mb_or_raise,
    get_or_create_session,
) -> str:
    """Manually trigger (or auto-trigger) an ingestion sync.

    Returns:
        job_id string for the newly created job.

    Raises:
        ValueError: If MemoryBase not found.
        RuntimeError: If a job is already active (caller should return 409).
    """
    async with session_scope() as db:
        mb = await get_mb_or_raise(db, memory_base_id, user_id)

        # Ensure a session record exists
        mbs = await get_or_create_session(db, memory_base_id, session_id)

        # Snapshot the cursor NOW (immutable arg for the task)
        cursor_id_snapshot = mbs.cursor_id

        # Build dedupe_key from the latest uncovered WORKFLOW run for idempotency.
        latest_job_id = await _get_latest_pending_workflow_job_id(db, mb, mbs)
        dedupe_key: str | None = None
        if latest_job_id is not None:
            dedupe_key = f"ingestion:{memory_base_id}:{session_id}:{latest_job_id}"

        kb_username = await resolve_kb_username(db, mb.user_id)
        embedding_provider, embedding_model = resolve_embedding(mb.kb_name, kb_username)

    # Create tracking job
    job_service = get_job_service()
    job_id = uuid.uuid4()
    await job_service.create_job(
        job_id=job_id,
        flow_id=mb.flow_id,
        user_id=mb.user_id,
        job_type=JobType.INGESTION,
        asset_id=memory_base_id,
        asset_type="memory_base",
        dedupe_key=dedupe_key,
    )

    task_service = get_task_service()
    await task_service.fire_and_forget_task(
        job_service.execute_with_status,
        job_id=job_id,
        run_coro_func=ingest_memory_task,
        request=IngestionRequest(
            memory_base_id=memory_base_id,
            session_id=session_id,
            flow_id=mb.flow_id,
            kb_name=mb.kb_name,
            kb_username=kb_username,
            user_id=mb.user_id,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            cursor_id=cursor_id_snapshot,
            task_job_id=job_id,
            job_service=job_service,
            preprocessing=mb.preprocessing,
            preproc_model=mb.preproc_model,
            preproc_instructions=mb.preproc_instructions,
            preproc_kill_phrase=mb.preproc_kill_phrase,
        ),
    )

    return str(job_id)


async def on_flow_output(
    flow_id: uuid.UUID,
    session_id: str,
    job_id: uuid.UUID | None,
    *,
    get_or_create_session,
) -> None:
    """Called after a flow run completes.

    For every MemoryBase watching this flow with auto_capture=True:
    1. Record the workflow run in the tracking table (inside _maybe_trigger).
    2. Count uncovered WORKFLOW runs for this session.
    3. If count >= threshold, fire ingestion task.
    """
    async with session_scope() as db:
        stmt = (
            select(MemoryBase).where(MemoryBase.flow_id == flow_id).where(MemoryBase.auto_capture == True)  # noqa: E712
        )
        result = await db.exec(stmt)
        memory_bases = list(result.all())

    hashed_sid = hash_session_id(session_id)
    for mb in memory_bases:
        try:
            await logger.adebug(
                "Auto-capture check | memory_base=%s threshold=%s session=%s",
                mb.id,
                mb.threshold,
                hashed_sid,
            )
            await _maybe_trigger(
                mb=mb, session_id=session_id, job_id=job_id, get_or_create_session=get_or_create_session
            )
        except (RuntimeError, ValueError, OSError):
            await logger.aerror("Auto-capture failed for memory_base=%s session=%s", mb.id, hashed_sid, exc_info=True)


async def _maybe_trigger(
    *,
    mb: MemoryBase,
    session_id: str,
    job_id: uuid.UUID | None,
    get_or_create_session,
) -> None:
    async with session_scope() as db:
        mbs = await get_or_create_session(db, mb.id, session_id)

        # Record this workflow run before evaluating the threshold.
        await _insert_workflow_run(db, mb.id, session_id, job_id)

        pending = await count_pending_messages(db, mb, mbs)

        if pending < mb.threshold:
            return

        cursor_id_snapshot = mbs.cursor_id

        # Build dedupe_key from the latest pending WORKFLOW run for idempotency.
        latest_wf_job_id = await _get_latest_pending_workflow_job_id(db, mb, mbs)
        dedupe_key: str | None = None
        if latest_wf_job_id is not None:
            dedupe_key = f"ingestion:{mb.id}:{session_id}:{latest_wf_job_id}"

        kb_username = await resolve_kb_username(db, mb.user_id)

    embedding_provider, embedding_model = resolve_embedding(mb.kb_name, kb_username)

    job_service = get_job_service()
    job_id = uuid.uuid4()
    try:
        await job_service.create_job(
            job_id=job_id,
            flow_id=mb.flow_id,
            user_id=mb.user_id,
            job_type=JobType.INGESTION,
            asset_id=mb.id,
            asset_type="memory_base",
            dedupe_key=dedupe_key,
        )
    except DuplicateJobError:
        await logger.adebug("Auto-capture: duplicate job for dedupe_key=%s - skipping.", dedupe_key)
        return

    task_service = get_task_service()
    await task_service.fire_and_forget_task(
        job_service.execute_with_status,
        job_id=job_id,
        run_coro_func=ingest_memory_task,
        request=IngestionRequest(
            memory_base_id=mb.id,
            session_id=session_id,
            flow_id=mb.flow_id,
            kb_name=mb.kb_name,
            kb_username=kb_username,
            user_id=mb.user_id,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            cursor_id=cursor_id_snapshot,
            task_job_id=job_id,
            job_service=job_service,
            preprocessing=mb.preprocessing,
            preproc_model=mb.preproc_model,
            preproc_instructions=mb.preproc_instructions,
            preproc_kill_phrase=mb.preproc_kill_phrase,
        ),
    )


async def check_mismatch(
    memory_base_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    get_mb_or_raise,
) -> bool:
    """Return True if metadata claims processed rows but vector store is empty."""
    async with session_scope() as db:
        mb = await get_mb_or_raise(db, memory_base_id, user_id)
        stmt = select(func.sum(MemoryBaseSession.total_processed)).where(
            MemoryBaseSession.memory_base_id == memory_base_id
        )
        result = await db.exec(stmt)
        total_processed: int = result.first() or 0

    if total_processed == 0:
        return False

    kb_username = await resolve_kb_username_by_user_id(user_id)
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        return False
    kb_path = kb_root / kb_username / mb.kb_name
    validate_kb_path(kb_root, kb_path)
    if not await asyncio.to_thread(kb_path.exists):
        return True

    metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
    return int(metadata.get("chunks", 0)) == 0


async def regenerate(
    memory_base_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    get_mb_or_raise,
    trigger_ingestion_fn,
) -> list[str]:
    """Reset all session cursors to None and re-trigger ingestion per session.

    Used to recover from FS / Vector DB mismatch (Chroma dir deleted externally).
    Returns list of newly created job IDs.
    Also deletes all MessageIngestionRecord rows for this memory base atomically
    with the cursor reset so that re-ingestion starts clean without hitting the
    unique constraint.
    """
    from sqlalchemy import delete as sa_delete

    from langflow.services.database.models.memory_base.model import (
        MemoryBasePreprocessingOutput,
        MessageIngestionRecord,
    )

    async with session_scope() as db:
        await get_mb_or_raise(db, memory_base_id, user_id)

        stmt = select(MemoryBaseSession).where(MemoryBaseSession.memory_base_id == memory_base_id)
        result = await db.exec(stmt)
        sessions = list(result.all())

        for s in sessions:
            s.cursor_id = None
            db.add(s)

        # Delete existing ingestion records so re-ingestion inserts fresh rows
        await db.exec(  # type: ignore[call-overload]
            sa_delete(MessageIngestionRecord).where(MessageIngestionRecord.memory_base_id == memory_base_id)
        )
        # Same for preprocessing outputs — without this, a stale "processed" row would
        # cause Phase A on the very next job to skip the LLM and retry with the old text.
        await db.exec(  # type: ignore[call-overload]
            sa_delete(MemoryBasePreprocessingOutput).where(
                MemoryBasePreprocessingOutput.memory_base_id == memory_base_id
            )
        )
        await db.commit()

    job_ids: list[str] = []
    for s in sessions:
        try:
            jid = await trigger_ingestion_fn(memory_base_id, user_id, s.session_id)
            job_ids.append(jid)
        except DuplicateJobError:
            await logger.awarning(
                "Regenerate: duplicate batch already ingested for session %s - skipped.",
                hash_session_id(s.session_id),
            )
        except RuntimeError:
            await logger.awarning(
                "Regenerate: active job exists for session %s - reset cursor but skipped trigger.",
                hash_session_id(s.session_id),
            )
    return job_ids


async def purge_session_data(
    *,
    user_id: uuid.UUID,
    session_ids: list[str],
) -> int:
    """Purge Chroma chunks and tracking rows for the given sessions across the user's MBs.

    Called from the message-session deletion endpoint so that wiping a session from
    the UI also clears its embeddings from every Memory Base that ingested from it.
    Without this, chunks tagged with the deleted session_id remain in Chroma and
    leak into newly-created sessions whose retrieval doesn't restrict by session_id.

    Returns the number of (memory_base, session) pairs that were processed.
    Best-effort: chunk deletion failures are logged but do not abort DB cleanup
    (we'd rather drop the bookkeeping rows than leave them dangling, since the
    user's intent — "delete this session" — is unambiguous).
    """
    from sqlalchemy import delete as sa_delete

    from langflow.services.database.models.memory_base.model import MessageIngestionRecord

    if not session_ids:
        return 0

    async with session_scope() as db:
        stmt = (
            select(MemoryBase, MemoryBaseSession)
            .join(MemoryBaseSession, MemoryBaseSession.memory_base_id == MemoryBase.id)
            .where(MemoryBase.user_id == user_id)
            .where(col(MemoryBaseSession.session_id).in_(session_ids))
        )
        result = await db.exec(stmt)
        pairs: list[tuple[MemoryBase, MemoryBaseSession]] = list(result.all())

        if not pairs:
            return 0

        kb_username = await resolve_kb_username(db, user_id)

    # ---- 1. Delete Chroma chunks (best-effort, outside the DB session) ----
    kb_root = KBStorageHelper.get_root_path()
    if kb_root:
        for mb, mbs in pairs:
            try:
                await _delete_chunks_for_session(
                    kb_root=kb_root,
                    kb_username=kb_username,
                    kb_name=mb.kb_name,
                    user_id=user_id,
                    session_id=mbs.session_id,
                )
            except (OSError, ValueError, chromadb.errors.ChromaError):
                await logger.aerror(
                    "Failed to purge chunks for memory_base=%s session=%s",
                    mb.id,
                    hash_session_id(mbs.session_id),
                    exc_info=True,
                )

    # ---- 2. Delete tracking rows in a single transaction ----
    pair_keys = [(mb.id, mbs.session_id) for mb, mbs in pairs]
    affected_mb_ids = {mb_id for mb_id, _ in pair_keys}
    affected_session_ids = {sid for _, sid in pair_keys}

    async with session_scope() as db:
        # Scheduler state, not audit: count_pending_messages keys on (memory_base_id, session_id)
        # string, so leaving these rows would carry pending counts into a future session that
        # reuses the same session_id and trigger a phantom ingestion. Audit lives on Job.
        await db.exec(  # type: ignore[call-overload]
            sa_delete(MemoryBaseWorkflowRun)
            .where(col(MemoryBaseWorkflowRun.memory_base_id).in_(affected_mb_ids))
            .where(col(MemoryBaseWorkflowRun.session_id).in_(affected_session_ids))
        )
        # Defensive: callers normally delete the underlying messages first (which cascades
        # MessageIngestionRecord via message.id FK), but if a caller invokes purge_session_data
        # without that, the records would leak and block re-ingestion via the unique constraint.
        await db.exec(  # type: ignore[call-overload]
            sa_delete(MessageIngestionRecord)
            .where(col(MessageIngestionRecord.memory_base_id).in_(affected_mb_ids))
            .where(col(MessageIngestionRecord.session_id).in_(affected_session_ids))
        )
        await db.exec(  # type: ignore[call-overload]
            sa_delete(MemoryBaseSession)
            .where(col(MemoryBaseSession.memory_base_id).in_(affected_mb_ids))
            .where(col(MemoryBaseSession.session_id).in_(affected_session_ids))
        )
        await db.commit()

    return len(pairs)


async def _delete_chunks_for_session(
    *,
    kb_root,
    kb_username: str,
    kb_name: str,
    user_id: uuid.UUID,
    session_id: str,
) -> None:
    """Open the KB's Chroma collection and delete every chunk tagged with ``session_id``.

    Uses the canonical ``$eq`` operator (matching the retrieval filter) so the
    delete and query paths agree on the metadata key shape.
    """
    kb_path = kb_root / kb_username / kb_name
    validate_kb_path(kb_root, kb_path)
    if not await asyncio.to_thread(kb_path.exists):
        return

    embedding_provider, embedding_model = resolve_embedding(kb_name, kb_username)
    user_stub = types.SimpleNamespace(id=user_id)
    embeddings = await KBIngestionHelper.build_embeddings(embedding_provider, embedding_model, user_stub)

    client = KBStorageHelper.get_fresh_chroma_client(kb_path)
    try:
        chroma = Chroma(
            client=client,
            embedding_function=embeddings,
            collection_name=kb_name,
            **chroma_langchain_collection_kwargs(),
        )
        await chroma.adelete(where={"session_id": {"$eq": session_id}})
        # Refresh on-disk metrics so the UI reflects the post-purge state.
        try:
            await asyncio.to_thread(_sync_metrics_after_purge, kb_path, chroma)
        except (OSError, ValueError):
            await logger.awarning(
                "Could not refresh KB metrics after session purge for %s/%s",
                kb_username,
                kb_name,
                exc_info=True,
            )
    finally:
        KBStorageHelper.release_chroma_resources(kb_path)


def _sync_metrics_after_purge(kb_path, chroma: Chroma) -> None:
    """Refresh chunk/word/character counts on the KB's embedding_metadata.json."""
    import json

    metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
    KBAnalysisHelper.update_text_metrics(kb_path, metadata, chroma=chroma)
    metadata["size"] = KBStorageHelper.get_directory_size(kb_path)
    (kb_path / "embedding_metadata.json").write_text(json.dumps(metadata, indent=2))


async def cancel_active_jobs(*, memory_base_id: uuid.UUID, db: AsyncSession) -> None:
    """Cancel all IN_PROGRESS or QUEUED jobs for this memory base."""
    stmt = (
        select(Job)
        .where(Job.asset_id == memory_base_id)
        .where(Job.asset_type == "memory_base")
        .where(col(Job.status).in_([JobStatus.IN_PROGRESS, JobStatus.QUEUED]))
    )
    result = await db.exec(stmt)
    active_jobs = list(result.all())

    task_service = get_task_service()
    job_service = get_job_service()
    for job in active_jobs:
        try:
            await task_service.revoke_task(job.job_id)
            await job_service.update_job_status(job.job_id, JobStatus.CANCELLED)
            await logger.ainfo("Cancelled job %s for memory_base %s", job.job_id, memory_base_id)
        except (RuntimeError, ValueError, OSError):
            await logger.awarning(
                "Could not cancel job %s for memory_base %s", job.job_id, memory_base_id, exc_info=True
            )


# ------------------------------------------------------------------ #
#  Shared query helpers (public — used by service.py and memories.py) #
# ------------------------------------------------------------------ #


async def count_pending_messages(db: AsyncSession, mb: MemoryBase, mbs: MemoryBaseSession) -> int:
    """Count WORKFLOW runs for this (memory_base, session) not yet covered by a completed ingestion.

    A row in memory_base_workflow_run with ingestion_job_id IS NULL means the run
    has not been processed by any ingestion job.  Count pending = number of such rows.
    This is session-scoped and time-independent; job failures leave rows NULL so they
    are correctly re-counted on the next threshold check.
    """
    stmt = (
        select(func.count())
        .select_from(MemoryBaseWorkflowRun)
        .where(MemoryBaseWorkflowRun.memory_base_id == mb.id)
        .where(MemoryBaseWorkflowRun.session_id == mbs.session_id)
        .where(MemoryBaseWorkflowRun.ingestion_job_id == None)  # noqa: E711
    )
    try:
        result = await db.exec(stmt)
        row = result.first()
        if row is None:
            return 0
        return int(row)
    except (TypeError, ValueError, OSError) as e:
        await logger.aerror("Error counting pending workflow runs: %s", e)
        return 0


async def _insert_workflow_run(
    db: AsyncSession,
    memory_base_id: uuid.UUID,
    session_id: str,
    job_id: uuid.UUID | None,
) -> None:
    """Record a WORKFLOW job run for (memory_base_id, session_id).

    Verifies that job_id refers to a WORKFLOW type job before inserting.
    Uses dialect-specific INSERT ... ON CONFLICT DO NOTHING for idempotency —
    safe to call multiple times with the same arguments.
    Skips silently if job_id is None or the job is not of WORKFLOW type.
    """
    from datetime import datetime, timezone

    hashed_sid = hash_session_id(session_id)
    if job_id is None:
        await logger.awarning(
            "on_flow_output called with no job_id for memory_base=%s session=%s — run not recorded.",
            memory_base_id,
            hashed_sid,
        )
        return

    job_result = await db.exec(select(Job).where(Job.job_id == job_id).where(Job.type == JobType.WORKFLOW))
    if job_result.first() is None:
        await logger.awarning(
            "job_id=%s is not a WORKFLOW job — skipping workflow run record for memory_base=%s session=%s.",
            job_id,
            memory_base_id,
            hashed_sid,
        )
        return

    row = {
        "id": uuid.uuid4(),
        "memory_base_id": memory_base_id,
        "session_id": session_id,
        "workflow_job_id": job_id,
        "ingestion_job_id": None,
        "recorded_at": datetime.now(timezone.utc),
    }
    conn = await db.connection()
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(MemoryBaseWorkflowRun).values([row]).on_conflict_do_nothing()
    else:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(MemoryBaseWorkflowRun).values([row]).on_conflict_do_nothing()
    await db.exec(stmt)  # type: ignore[call-overload]
    await db.commit()


async def _get_latest_pending_workflow_job_id(
    db: AsyncSession, mb: MemoryBase, mbs: MemoryBaseSession
) -> uuid.UUID | None:
    """Return the workflow_job_id of the most recent uncovered workflow run for this session."""
    stmt = (
        select(MemoryBaseWorkflowRun.workflow_job_id)
        .where(MemoryBaseWorkflowRun.memory_base_id == mb.id)
        .where(MemoryBaseWorkflowRun.session_id == mbs.session_id)
        .where(MemoryBaseWorkflowRun.ingestion_job_id == None)  # noqa: E711
        .order_by(col(MemoryBaseWorkflowRun.recorded_at).desc())
        .limit(1)
    )
    result = await db.exec(stmt)
    return result.first()
