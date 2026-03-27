"""MemoryBase service – business logic for CRUD and ingestion orchestration.

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
from pathlib import Path

from lfx.log.logger import logger
from sqlmodel import col, distinct, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBStorageHelper
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBaseCreate,
    MemoryBaseSession,
    MemoryBaseSessionRead,
    MemoryBaseUpdate,
)
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_job_service, get_task_service, session_scope
from langflow.services.memory_base.task import ingest_memory_task

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
        async with session_scope() as db:
            # 1. Name uniqueness per user
            existing = await db.exec(
                select(MemoryBase).where(MemoryBase.user_id == user_id).where(MemoryBase.name == payload.name)
            )
            if existing.first() is not None:
                msg = f"A Memory Base named '{payload.name}' already exists for this user"
                raise ValueError(msg)

            # 2. Resolve username for KB path
            kb_username = await self._resolve_kb_username(db, user_id)

        # 3. Auto-generate kb_name: sanitized_name_<8hex>
        kb_name = f"{_sanitize_kb_name(payload.name)}_{uuid.uuid4().hex[:8]}"

        # 4. Create KB directory and embedding_metadata.json on disk
        embedding_provider = _infer_embedding_provider(payload.embedding_model)
        await self._initialize_kb(
            kb_name=kb_name,
            kb_username=kb_username,
            embedding_provider=embedding_provider,
            embedding_model=payload.embedding_model,
        )

        # 5. Persist DB record
        async with session_scope() as db:
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

    def list_for_user_stmt(self, user_id: uuid.UUID):  # type: ignore[return]
        """Return the SQLModel select statement for pagination at the API layer."""
        return select(MemoryBase).where(MemoryBase.user_id == user_id)

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
        except Exception:
            await logger.awarning(
                "Could not delete KB '%s' from disk after Memory Base deletion.", kb_name, exc_info=True
            )

    # ------------------------------------------------------------------ #
    #  Sessions                                                             #
    # ------------------------------------------------------------------ #

    async def get_sessions(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> list[MemoryBaseSessionRead]:
        """Return all sessions with pending message counts.

        Includes sessions that have messages in MessageTable for the associated
        flow but no MemoryBaseSession record yet (i.e. never synced).
        All messages are counted (not just is_output) to match the full
        conversation batch ingestion approach.
        """
        async with session_scope() as db:
            # Verify ownership
            mb = await self._get_mb_or_raise(db, memory_base_id, user_id)

            # All tracked sessions
            stmt = select(MemoryBaseSession).where(MemoryBaseSession.memory_base_id == memory_base_id)
            result = await db.exec(stmt)
            tracked = list(result.all())
            tracked_ids = {s.session_id for s in tracked}

            # All sessions that have any flow messages (may include untracked ones)
            dist_stmt = select(distinct(MessageTable.session_id)).where(
                MessageTable.flow_id == mb.flow_id,
            )
            dist_result = await db.exec(dist_stmt)
            all_session_ids: set[str] = {row for row in dist_result.all() if row}

            output: list[MemoryBaseSessionRead] = []

            # Tracked sessions — compute pending count from cursor
            for s in tracked:
                pending = await self._count_pending(db, mb, s)
                output.append(
                    MemoryBaseSessionRead(
                        id=s.id,
                        memory_base_id=s.memory_base_id,
                        session_id=s.session_id,
                        cursor_id=s.cursor_id,
                        total_processed=s.total_processed,
                        last_sync_at=s.last_sync_at,
                        pending_count=pending,
                    )
                )

            # Untracked sessions — all their messages are pending
            for sid in sorted(all_session_ids - tracked_ids):
                count_stmt = (
                    select(func.count())
                    .select_from(MessageTable)
                    .where(MessageTable.flow_id == mb.flow_id)
                    .where(MessageTable.session_id == sid)
                )
                count_result = await db.exec(count_stmt)
                pending = count_result.one()
                output.append(
                    MemoryBaseSessionRead(
                        id=uuid.uuid4(),  # Synthetic — no DB row yet
                        memory_base_id=memory_base_id,
                        session_id=sid,
                        cursor_id=None,
                        total_processed=0,
                        last_sync_at=None,
                        pending_count=pending,
                    )
                )

            return output

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

            # Concurrent task prevention – one active job per (memory_base_id, session_id)
            if await self._has_active_job(db, memory_base_id, session_id):
                msg = f"Ingestion already in progress for memory_base={memory_base_id} session={session_id}"
                raise RuntimeError(msg)

            # Ensure a session record exists
            mbs = await self._get_or_create_session(db, memory_base_id, session_id)

            # Snapshot the cursor NOW (immutable arg for the task)
            cursor_id_snapshot = mbs.cursor_id

            kb_username = await self._resolve_kb_username(db, mb.user_id)
            embedding_provider, embedding_model = self._resolve_embedding(mb.kb_name, kb_username)

        # Create tracking job
        job_service = get_job_service()
        job_id = uuid.uuid4()
        await job_service.create_job(
            job_id=job_id,
            flow_id=mb.flow_id,
            job_type=JobType.INGESTION,
            asset_id=memory_base_id,
            asset_type="memory_base",
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
        run_id: uuid.UUID | None,
    ) -> None:
        """Called after flow output messages are persisted.

        For every MemoryBase watching this flow with auto_capture=True:
        1. Ensure a MemoryBaseSession exists.
        2. Count pending output messages for the session.
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
                await self._maybe_trigger(mb=mb, session_id=session_id)
            except Exception:
                await logger.aerror(
                    "Auto-capture failed for memory_base=%s session=%s", mb.id, session_id, exc_info=True
                )

    async def _maybe_trigger(self, *, mb: MemoryBase, session_id: str) -> None:
        async with session_scope() as db:
            mbs = await self._get_or_create_session(db, mb.id, session_id)
            pending = await self._count_pending(db, mb, mbs)

            if pending < mb.threshold:
                return

            if await self._has_active_job(db, mb.id, session_id):
                await logger.adebug(
                    "Auto-capture: job already active for memory_base=%s session=%s – skipping.", mb.id, session_id
                )
                return

            cursor_id_snapshot = mbs.cursor_id
            kb_username = await self._resolve_kb_username(db, mb.user_id)

        embedding_provider, embedding_model = self._resolve_embedding(mb.kb_name, kb_username)

        job_service = get_job_service()
        job_id = uuid.uuid4()
        await job_service.create_job(
            job_id=job_id,
            flow_id=mb.flow_id,
            job_type=JobType.INGESTION,
            asset_id=mb.id,
            asset_type="memory_base",
        )

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
        """
        async with session_scope() as db:
            mb = await self._get_mb_or_raise(db, memory_base_id, user_id)

            stmt = select(MemoryBaseSession).where(MemoryBaseSession.memory_base_id == memory_base_id)
            result = await db.exec(stmt)
            sessions = list(result.all())

            for s in sessions:
                s.cursor_id = None
                db.add(s)
            await db.commit()

        job_ids: list[str] = []
        for s in sessions:
            try:
                jid = await self.trigger_ingestion(memory_base_id, user_id, s.session_id)
                job_ids.append(jid)
            except RuntimeError:
                await logger.awarning(
                    "Regenerate: active job exists for session %s – reset cursor but skipped trigger.", s.session_id
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

    async def _count_pending(self, db: AsyncSession, mb: MemoryBase, mbs: MemoryBaseSession) -> int:
        """Count all messages for this session that come after the cursor.

        is_output filtering is intentionally omitted: we ingest the full
        conversation batch (both user and model turns) so the KB reflects the
        complete context of each run.  is_output-only filtering will be
        re-evaluated in a future iteration once the flag is reliably set.
        """
        stmt = (
            select(func.count())
            .select_from(MessageTable)
            .where(MessageTable.flow_id == mb.flow_id)
            .where(MessageTable.session_id == mbs.session_id)
        )
        if mbs.cursor_id is not None:
            cursor_stmt = select(MessageTable.timestamp).where(MessageTable.id == mbs.cursor_id)
            cursor_result = await db.exec(cursor_stmt)
            cursor_ts = cursor_result.first()
            if cursor_ts:
                stmt = stmt.where(col(MessageTable.timestamp) > cursor_ts)

        result = await db.exec(stmt)
        return result.one()

    async def _has_active_job(self, db: AsyncSession, memory_base_id: uuid.UUID, session_id: str) -> bool:
        """Check whether an ingestion job is already IN_PROGRESS for this (mb, session)."""
        stmt = (
            select(func.count())
            .select_from(Job)
            .where(Job.asset_id == memory_base_id)
            .where(Job.asset_type == "memory_base")
            .where(Job.status == JobStatus.IN_PROGRESS)
        )
        result = await db.exec(stmt)
        return result.one() > 0

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
            except Exception:
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
