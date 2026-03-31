"""MemoryBase service - business logic for CRUD and ingestion orchestration.

Edge cases handled:
- Name uniqueness per user: 409 if a Memory Base with the same name already exists.
- Deletion during sync: cancels active tasks before DB deletion.
- KB deletion on delete: removes the associated KB directory from disk.
- Concurrent task prevention: returns 409 if a job is already IN_PROGRESS.
- Threshold updates: deferred; does not re-evaluate pending count immediately.
- FS / Vector DB mismatch: detects and surfaces a warning flag.
- Regenerate: resets all session cursors to None and re-triggers ingestion.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlmodel import col, func, select

from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBStorageHelper
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBaseCreate,
    MemoryBaseSession,
    MemoryBaseUpdate,
    MemoryBaseWorkflowRun,
)
from langflow.services.deps import get_job_service, get_task_service, session_scope
from langflow.services.jobs import DuplicateJobError
from langflow.services.memory_base.task import ingest_memory_task

if TYPE_CHECKING:
    from pathlib import Path

    from sqlmodel.ext.asyncio.session import AsyncSession

# Provider inference map — mirrors provider_patterns in KBAnalysisHelper._detect_embedding_provider
# so we can derive the provider from a model name string without filesystem access.
_MODEL_TO_PROVIDER: list[tuple[list[str], str]] = [
    (["text-embedding", "ada-", "gpt-"], "OpenAI"),
    (["embed-english", "embed-multilingual"], "Cohere"),
    (["sentence-transformers", "bert-", "huggingface"], "HuggingFace"),
    (["palm", "gecko", "google"], "Google"),
    (["ollama"], "Ollama"),
    (["azure"], "Azure OpenAI"),
]


def _infer_embedding_provider(embedding_model: str) -> str:
    """Derive embedding provider name from a model string."""
    lower = embedding_model.lower()
    for patterns, provider in _MODEL_TO_PROVIDER:
        if any(p in lower for p in patterns):
            return provider
    return "OpenAI"  # Safe default — matches _resolve_embedding fallback


def _sanitize_kb_name(name: str) -> str:
    """Lowercase, replace spaces/hyphens with underscores, strip non-alphanum."""
    sanitized = name.strip().lower()
    sanitized = re.sub(r"[\s\-]+", "_", sanitized)
    sanitized = re.sub(r"[^\w]", "", sanitized)
    return sanitized or "memory"


class MemoryBaseService:
    """Service layer for MemoryBase CRUD and ingestion orchestration."""

    # ------------------------------------------------------------------ #
    #  CRUD                                                                 #
    # ------------------------------------------------------------------ #

    async def create(self, payload: MemoryBaseCreate, user_id: uuid.UUID) -> MemoryBase:
        # 1. Verify that the referenced flow belongs to this user.  Without this
        #    check a user could point a Memory Base at another user's flow and then
        #    read captured conversation history via /sessions + /messages.
        #    Raises PermissionError (→ 404 at the API layer to avoid info-leak) if
        #    the flow does not exist or is not owned by user_id.
        async with session_scope() as db:
            from langflow.services.database.models.flow.model import Flow

            flow_result = await db.exec(select(Flow).where(Flow.id == payload.flow_id).where(Flow.user_id == user_id))
            if flow_result.first() is None:
                msg = f"Flow {payload.flow_id} not found"
                raise PermissionError(msg)

        # 2. Resolve username — needed for the KB path, separate session so the
        #    connection is not held open during disk I/O below.
        async with session_scope() as db:
            kb_username = await self._resolve_kb_username(db, user_id)

        # 2. Auto-generate kb_name: sanitized_name_<8hex>
        kb_name = f"{_sanitize_kb_name(payload.name)}_{uuid.uuid4().hex[:8]}"

        # 3. Create KB directory and embedding_metadata.json on disk (best-effort).
        #    KB init runs before the DB insert — if the insert later fails, the
        #    orphaned directory is harmless (nothing writes to it without a DB record).
        embedding_provider = _infer_embedding_provider(payload.embedding_model)
        await self._initialize_kb(
            kb_name=kb_name,
            kb_username=kb_username,
            embedding_provider=embedding_provider,
            embedding_model=payload.embedding_model,
        )

        # 4. Uniqueness check + insert in ONE session_scope to close the TOCTOU window.
        #    Both the SELECT and the INSERT see the same DB snapshot; a concurrent
        #    create with the same name is caught by the re-check here.
        async with session_scope() as db:
            existing = await db.exec(
                select(MemoryBase).where(MemoryBase.user_id == user_id).where(MemoryBase.name == payload.name)
            )
            if existing.first() is not None:
                msg = f"A Memory Base named '{payload.name}' already exists for this user"
                raise ValueError(msg)

            mb = MemoryBase(
                **payload.model_dump(exclude={"user_id"}),
                user_id=user_id,
                kb_name=kb_name,
            )
            db.add(mb)
            await db.commit()
            await db.refresh(mb)

        return mb

    async def _initialize_kb(
        self,
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
        kb_path.mkdir(parents=True, exist_ok=True)

        # Initialize Chroma collection so the directory is non-empty and readable
        try:
            client = KBStorageHelper.get_fresh_chroma_client(kb_path)
            client.create_collection(name=kb_name)
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
        (kb_path / "embedding_metadata.json").write_text(json.dumps(embedding_metadata, indent=2))

    async def list_for_user(self, user_id: uuid.UUID) -> list[MemoryBase]:
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            return list(result.all())

    def list_for_user_stmt(self, user_id: uuid.UUID, flow_id: uuid.UUID | None = None):  # type: ignore[return]
        """Return the SQLModel select statement for pagination at the API layer."""
        stmt = select(MemoryBase).where(MemoryBase.user_id == user_id)
        if flow_id is not None:
            stmt = stmt.where(MemoryBase.flow_id == flow_id)
        return stmt

    async def get(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> MemoryBase | None:
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            return result.first()

    async def update(
        self,
        memory_base_id: uuid.UUID,
        user_id: uuid.UUID,
        patch: MemoryBaseUpdate,
    ) -> MemoryBase | None:
        """Update mutable fields.

        Threshold changes take effect on the NEXT auto-capture trigger; any
        already-running ingestion task ignores the change (immutable args).
        """
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            mb = result.first()
            if mb is None:
                return None
            for field, value in patch.model_dump(exclude_unset=True).items():
                setattr(mb, field, value)
            db.add(mb)
            await db.commit()
            await db.refresh(mb)
            return mb

    async def delete(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a MemoryBase and its associated KB directory.

        Edge cases:
        - If a sync task is active, cancel it BEFORE committing the DB deletion.
        - KB directory deletion is best-effort after the DB commit — a failure
          is logged but not re-raised so the caller always gets a clean 204.
        """
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            mb = result.first()
            if mb is None:
                return False

            kb_name = mb.kb_name
            kb_username = await self._resolve_kb_username(db, user_id)

            # Cancel active ingestion jobs before removing the DB record
            await self._cancel_active_jobs(memory_base_id=memory_base_id, db=db)

            await db.delete(mb)
            await db.commit()

        # Delete the corresponding KB from disk (best-effort — DB already committed)
        await self._delete_kb(kb_name=kb_name, kb_username=kb_username)

        return True

    async def _delete_kb(self, *, kb_name: str, kb_username: str) -> None:
        """Remove the KB directory from disk. Logs on failure, does not raise."""
        if not kb_name:
            return
        kb_root = KBStorageHelper.get_root_path()
        if not kb_root:
            return
        kb_path = kb_root / kb_username / kb_name
        try:
            KBStorageHelper.delete_storage(kb_path, kb_name)
        except (OSError, ValueError):
            await logger.awarning(
                "Could not delete KB '%s' from disk after Memory Base deletion.", kb_name, exc_info=True
            )

    # ------------------------------------------------------------------ #
    #  Sessions                                                             #
    # ------------------------------------------------------------------ #

    async def verify_ownership(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Raise ValueError if the Memory Base does not belong to user_id."""
        async with session_scope() as db:
            await self._get_mb_or_raise(db, memory_base_id, user_id)

    def sessions_stmt(self, memory_base_id: uuid.UUID):  # type: ignore[return]
        """Return the select statement for persisted sessions, for use with apaginate."""
        return (
            select(MemoryBaseSession)
            .where(MemoryBaseSession.memory_base_id == memory_base_id)
            .order_by(col(MemoryBaseSession.last_sync_at).desc())
        )

    # ------------------------------------------------------------------ #
    #  Ingestion                                                            #
    # ------------------------------------------------------------------ #

    async def trigger_ingestion(
        self,
        memory_base_id: uuid.UUID,
        user_id: uuid.UUID,
        session_id: str,
    ) -> str:
        """Manually trigger (or auto-trigger) an ingestion sync.

        Returns:
            job_id string for the newly created job.

        Raises:
            ValueError: If MemoryBase not found.
            RuntimeError: If a job is already active (caller should return 409).
        """
        async with session_scope() as db:
            mb = await self._get_mb_or_raise(db, memory_base_id, user_id)

            # Ensure a session record exists
            mbs = await self._get_or_create_session(db, memory_base_id, session_id)

            # Snapshot the cursor NOW (immutable arg for the task)
            cursor_id_snapshot = mbs.cursor_id

            # Build dedupe_key from the latest uncovered WORKFLOW run for idempotency.
            # Format: "ingestion:{memory_base_id}:{session_id}:{latest_workflow_job_id}"
            # Uniqueness: job type prefix + MB scope + session scope + batch identity.
            # Dedup enforcement (QUEUED/IN_PROGRESS/COMPLETED) happens inside create_job().
            # Retries are allowed when the prior job was FAILED or CANCELLED.
            latest_job_id = await self._get_latest_pending_workflow_job_id(db, mb, mbs)
            dedupe_key: str | None = None
            if latest_job_id is not None:
                dedupe_key = f"ingestion:{memory_base_id}:{session_id}:{latest_job_id}"

            kb_username = await self._resolve_kb_username(db, mb.user_id)
            embedding_provider, embedding_model = self._resolve_embedding(mb.kb_name, kb_username)

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
        )

        return str(job_id)

    # ------------------------------------------------------------------ #
    #  Auto-capture hook (called from flow execution engine)               #
    # ------------------------------------------------------------------ #

    async def on_flow_output(
        self,
        flow_id: uuid.UUID,
        session_id: str,
        job_id: uuid.UUID | None,
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

        for mb in memory_bases:
            try:
                await logger.adebug(
                    "Auto-capture check | memory_base=%s name=%r threshold=%s session=%s",
                    mb.id,
                    mb.name,
                    mb.threshold,
                    session_id,
                )
                await self._maybe_trigger(mb=mb, session_id=session_id, job_id=job_id)
            except (RuntimeError, ValueError, OSError):
                await logger.aerror(
                    "Auto-capture failed for memory_base=%s session=%s", mb.id, session_id, exc_info=True
                )

    async def _maybe_trigger(self, *, mb: MemoryBase, session_id: str, job_id: uuid.UUID | None) -> None:
        async with session_scope() as db:
            mbs = await self._get_or_create_session(db, mb.id, session_id)

            # Record this workflow run before evaluating the threshold.
            await self._insert_workflow_run(db, mb.id, session_id, job_id)

            pending = await self._count_pending(db, mb, mbs)

            if pending < mb.threshold:
                return

            cursor_id_snapshot = mbs.cursor_id

            # Build dedupe_key from the latest pending WORKFLOW run for idempotency.
            latest_wf_job_id = await self._get_latest_pending_workflow_job_id(db, mb, mbs)
            dedupe_key: str | None = None
            if latest_wf_job_id is not None:
                dedupe_key = f"ingestion:{mb.id}:{session_id}:{latest_wf_job_id}"

            kb_username = await self._resolve_kb_username(db, mb.user_id)

        embedding_provider, embedding_model = self._resolve_embedding(mb.kb_name, kb_username)

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
        )

    # ------------------------------------------------------------------ #
    #  FS / Vector DB mismatch detection                                   #
    # ------------------------------------------------------------------ #

    async def check_mismatch(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return True if metadata claims processed rows but vector store is empty.

        The UI should surface a "Mismatch Detected" warning and offer Regenerate.
        """
        async with session_scope() as db:
            mb = await self._get_mb_or_raise(db, memory_base_id, user_id)
            stmt = select(func.sum(MemoryBaseSession.total_processed)).where(
                MemoryBaseSession.memory_base_id == memory_base_id
            )
            result = await db.exec(stmt)
            total_processed: int = result.first() or 0

        if total_processed == 0:
            return False

        kb_username = await self._resolve_kb_username_by_user_id(user_id)
        kb_root = KBStorageHelper.get_root_path()
        if not kb_root:
            return False
        kb_path = kb_root / kb_username / mb.kb_name
        if not kb_path.exists():
            return True

        metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
        return int(metadata.get("chunks", 0)) == 0

    async def regenerate(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> list[str]:
        """Reset all session cursors to None and re-trigger ingestion per session.

        Used to recover from FS / Vector DB mismatch (Chroma dir deleted externally).
        Returns list of newly created job IDs.
        Also deletes all MessageIngestionRecord rows for this memory base atomically
        with the cursor reset so that re-ingestion starts clean without hitting the
        unique constraint.
        """
        from sqlalchemy import delete as sa_delete

        from langflow.services.database.models.memory_base.model import MessageIngestionRecord

        async with session_scope() as db:
            await self._get_mb_or_raise(db, memory_base_id, user_id)

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
            await db.commit()

        job_ids: list[str] = []
        for s in sessions:
            try:
                jid = await self.trigger_ingestion(memory_base_id, user_id, s.session_id)
                job_ids.append(jid)
            except DuplicateJobError:
                await logger.awarning(
                    "Regenerate: duplicate batch already ingested for session %s - skipped.", s.session_id
                )
            except RuntimeError:
                await logger.awarning(
                    "Regenerate: active job exists for session %s - reset cursor but skipped trigger.", s.session_id
                )
        return job_ids

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _get_mb_or_raise(self, db: AsyncSession, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> MemoryBase:
        stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == user_id)
        result = await db.exec(stmt)
        mb = result.first()
        if mb is None:
            msg = f"MemoryBase {memory_base_id} not found"
            raise ValueError(msg)
        return mb

    async def _get_or_create_session(
        self, db: AsyncSession, memory_base_id: uuid.UUID, session_id: str
    ) -> MemoryBaseSession:
        stmt = (
            select(MemoryBaseSession)
            .where(MemoryBaseSession.memory_base_id == memory_base_id)
            .where(MemoryBaseSession.session_id == session_id)
        )
        result = await db.exec(stmt)
        mbs = result.first()
        if mbs is None:
            mbs = MemoryBaseSession(memory_base_id=memory_base_id, session_id=session_id)
            db.add(mbs)
            await db.commit()
            await db.refresh(mbs)
        return mbs

    async def _insert_workflow_run(
        self,
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
        if job_id is None:
            await logger.awarning(
                "on_flow_output called with no job_id for memory_base=%s session=%s — run not recorded.",
                memory_base_id,
                session_id,
            )
            return

        job_result = await db.exec(select(Job).where(Job.job_id == job_id).where(Job.type == JobType.WORKFLOW))
        if job_result.first() is None:
            await logger.awarning(
                "job_id=%s is not a WORKFLOW job — skipping workflow run record for memory_base=%s session=%s.",
                job_id,
                memory_base_id,
                session_id,
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

    async def _count_pending(self, db: AsyncSession, mb: MemoryBase, mbs: MemoryBaseSession) -> int:
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

    async def _get_latest_pending_workflow_job_id(
        self, db: AsyncSession, mb: MemoryBase, mbs: MemoryBaseSession
    ) -> uuid.UUID | None:
        """Return the workflow_job_id of the most recent uncovered workflow run for this session.

        Used to build a stable dedupe key for the ingestion job so that the same
        batch of runs cannot trigger duplicate ingestion jobs.
        """
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

    async def _cancel_active_jobs(self, *, memory_base_id: uuid.UUID, db: AsyncSession) -> None:
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

    async def _resolve_kb_username(self, db: AsyncSession, user_id: uuid.UUID) -> str:
        from langflow.services.database.models.user.model import User

        stmt = select(User.username).where(User.id == user_id)
        result = await db.exec(stmt)
        username = result.first()
        if not username:
            msg = f"User {user_id} not found"
            raise ValueError(msg)
        return username

    async def _resolve_kb_username_by_user_id(self, user_id: uuid.UUID) -> str:
        async with session_scope() as db:
            return await self._resolve_kb_username(db, user_id)

    def _resolve_embedding(self, kb_name: str, kb_username: str) -> tuple[str, str]:
        """Read embedding provider/model from KB metadata.json, with sane defaults."""
        kb_root = KBStorageHelper.get_root_path()
        if not kb_root:
            return "OpenAI", "text-embedding-3-small"
        kb_path: Path = kb_root / kb_username / kb_name
        metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
        provider = metadata.get("embedding_provider") or "OpenAI"
        model = metadata.get("embedding_model") or "text-embedding-3-small"
        return provider, model
