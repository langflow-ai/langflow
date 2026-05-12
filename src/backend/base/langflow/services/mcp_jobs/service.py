"""MCP job executor service.

Drains ``mcp_jobs`` rows in state ``pending``, runs the referenced flow via the
existing ``simple_run_flow`` API, and persists ``running``/``completed``/
``failed`` transitions. Backed by a bounded asyncio worker pool — no external
queue dependency, so this works in the default SQLite single-process
deployment as well as Postgres-backed multi-worker deployments.

See ``docs/docs/Agents/mcp-catalog-and-long-running.mdx`` for the design.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
from lfx.log.logger import logger
from sqlalchemy import select, update

from langflow.services.base import Service
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.mcp_job.model import MCPJob, MCPJobStatus

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


def _get_db_service():
    """Lazy accessor for the DB service.

    Imported at call time to break the circular import between this module and
    ``langflow.services.deps`` (deps eagerly imports this service for its
    return-type annotation, which would otherwise re-enter this module while
    deps is still initializing).
    """
    from langflow.services.deps import get_db_service

    return get_db_service()


_DEFAULT_WORKERS = 4
_POLL_INTERVAL_S = 1.0
_PROGRESS_INTERVAL_S = 1.0
_CALLBACK_RETRIES = 3
_CALLBACK_TIMEOUT_S = 10.0
_CALLBACK_RETRY_ON_STATUS_BELOW = 500


def _worker_count() -> int:
    """Worker pool size, configurable via ``LANGFLOW_MCP_JOB_WORKERS``."""
    raw = os.environ.get("LANGFLOW_MCP_JOB_WORKERS")
    if not raw:
        return _DEFAULT_WORKERS
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "LANGFLOW_MCP_JOB_WORKERS=%r is not an int; falling back to %d",
            raw,
            _DEFAULT_WORKERS,
        )
        return _DEFAULT_WORKERS
    return max(1, min(value, 64))


def _allow_http_callback() -> bool:
    return os.environ.get("LANGFLOW_MCP_JOB_ALLOW_HTTP_CALLBACK", "false").lower() == "true"


class MCPJobExecutorService(Service):
    """Persistent MCP job executor — claim, run, persist, callback."""

    name = "mcp_jobs_service"

    def __init__(self) -> None:
        self._workers: list[asyncio.Task] = []
        self._shutdown = asyncio.Event()
        self._started = False

    def is_started(self) -> bool:
        return self._started

    async def start(self) -> None:
        if self._started:
            return
        await self._reconcile_orphaned_running_jobs()
        self._shutdown.clear()
        workers = _worker_count()
        for i in range(workers):
            self._workers.append(asyncio.create_task(self._worker_loop(i)))
        self._started = True
        await logger.adebug("MCPJobExecutorService started with %d workers", workers)

    async def stop(self) -> None:
        self._shutdown.set()
        for task in self._workers:
            task.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._started = False

    async def teardown(self) -> None:
        await self.stop()

    async def _reconcile_orphaned_running_jobs(self) -> None:
        """Transition any ``running`` jobs from a previous process to ``failed``.

        First-cut behavior: long-running jobs are not resumable across Langflow
        restarts. A row in ``running`` at startup means the previous process
        exited without finishing the job — mark it failed with a clear error so
        the client polling endpoint sees the terminal state.
        """
        now = datetime.now(timezone.utc)
        db = _get_db_service()
        async with db.with_session() as session:
            stmt = (
                update(MCPJob)
                .where(MCPJob.status == MCPJobStatus.RUNNING)
                .values(
                    status=MCPJobStatus.FAILED,
                    error="langflow restarted before completion",
                    updated_at=now,
                    completed_at=now,
                )
            )
            await session.exec(stmt)
            await session.commit()

    async def _worker_loop(self, worker_idx: int) -> None:
        await logger.adebug("MCPJobExecutor worker %d started", worker_idx)
        while not self._shutdown.is_set():
            try:
                job_id = await self._claim_next_pending_job()
            except Exception as exc:  # noqa: BLE001
                await logger.aerror("MCPJobExecutor worker %d claim failed: %s", worker_idx, exc)
                await asyncio.sleep(_POLL_INTERVAL_S)
                continue

            if job_id is None:
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._shutdown.wait(), timeout=_POLL_INTERVAL_S)
                continue

            try:
                await self._run_job(job_id)
            except asyncio.CancelledError:
                # Shutdown mid-job: mark failed so the row doesn't dangle.
                await self._finalize_job(job_id, MCPJobStatus.FAILED, error="worker cancelled during shutdown")
                raise
            except Exception as exc:  # noqa: BLE001
                await logger.aexception("MCPJobExecutor worker %d job %s failed: %s", worker_idx, job_id, exc)
                await self._finalize_job(job_id, MCPJobStatus.FAILED, error=str(exc)[:4096])

    async def _claim_next_pending_job(self) -> UUID | None:
        """Atomically transition one pending job to ``running``.

        Two-step: SELECT the oldest pending id, then UPDATE conditional on the
        status still being ``pending``. The UPDATE's affected-row count tells
        us whether another worker grabbed it first. Works on SQLite and
        Postgres without dialect-specific locking.
        """
        now = datetime.now(timezone.utc)
        db = _get_db_service()
        async with db.with_session() as session:
            session: AsyncSession  # type: ignore[no-redef]
            stmt = select(MCPJob.id).where(MCPJob.status == MCPJobStatus.PENDING).order_by(MCPJob.created_at).limit(1)
            result = await session.exec(stmt)
            row = result.first()
            if row is None:
                return None
            candidate_id: UUID = row if isinstance(row, UUID) else row[0]

            update_stmt = (
                update(MCPJob)
                .where(MCPJob.id == candidate_id, MCPJob.status == MCPJobStatus.PENDING)
                .values(status=MCPJobStatus.RUNNING, updated_at=now)
            )
            update_result = await session.exec(update_stmt)
            await session.commit()
            if getattr(update_result, "rowcount", 0) == 0:
                return None
            return candidate_id

    async def _run_job(self, job_id: UUID) -> None:
        # Local imports avoid pulling the heavy flow execution stack at module load.
        from langflow.api.v1.endpoints import simple_run_flow
        from langflow.api.v1.schemas import SimplifiedAPIRequest
        from langflow.schema.message import Message
        from langflow.services.database.models.user.model import User

        db = _get_db_service()
        async with db.with_session() as session:
            job = await session.get(MCPJob, job_id)
            if job is None:
                return
            flow = await session.get(Flow, job.flow_id)
            if flow is None:
                await self._finalize_job(job_id, MCPJobStatus.FAILED, error="flow no longer exists")
                return
            user: User | None = None
            if job.created_by is not None:
                user = await session.get(User, job.created_by)
            inputs = dict(job.inputs)
            timeout_s = flow.default_timeout_s or 3600
            callback_url = job.callback_url

        input_request = SimplifiedAPIRequest(
            input_value=inputs.get("input_value", ""),
            session_id=str(job_id),
        )
        progress_task = asyncio.create_task(self._tick_progress(job_id))
        try:
            try:
                result = await asyncio.wait_for(
                    simple_run_flow(
                        flow=flow,
                        input_request=input_request,
                        stream=False,
                        api_key_user=user,
                    ),
                    timeout=timeout_s,
                )
            except asyncio.TimeoutError:
                await self._finalize_job(job_id, MCPJobStatus.FAILED, error=f"timed out after {timeout_s}s")
                return

            collected: list[str] = []
            seen: set[str] = set()

            def _push(text: str) -> None:
                if text not in seen:
                    seen.add(text)
                    collected.append(text)

            for run_output in result.outputs:
                for component_output in run_output.outputs:
                    for msg in component_output.messages or []:
                        _push(msg.message)
                    for value in (component_output.results or {}).values():
                        if isinstance(value, Message):
                            _push(value.get_text())
                        else:
                            _push(str(value))

            payload = {"texts": collected}
            await self._finalize_job(job_id, MCPJobStatus.COMPLETED, result=payload)
        finally:
            progress_task.cancel()
            await asyncio.gather(progress_task, return_exceptions=True)

        if callback_url:
            await self._fire_callback(job_id, callback_url)

    async def _tick_progress(self, job_id: UUID) -> None:
        progress = 0
        while True:
            await asyncio.sleep(_PROGRESS_INTERVAL_S)
            progress = min(90, progress + 10)
            db = _get_db_service()
            async with db.with_session() as session:
                stmt = (
                    update(MCPJob)
                    .where(MCPJob.id == job_id, MCPJob.status == MCPJobStatus.RUNNING)
                    .values(progress=progress, updated_at=datetime.now(timezone.utc))
                )
                await session.exec(stmt)
                await session.commit()

    async def _finalize_job(
        self,
        job_id: UUID,
        status: MCPJobStatus,
        *,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        values: dict = {
            "status": status,
            "updated_at": now,
            "completed_at": now,
            "progress": 100 if status == MCPJobStatus.COMPLETED else 0,
        }
        if result is not None:
            values["result"] = result
        if error is not None:
            values["error"] = error[:4096]
        db = _get_db_service()
        async with db.with_session() as session:
            stmt = update(MCPJob).where(MCPJob.id == job_id).values(**values)
            await session.exec(stmt)
            await session.commit()

    async def _fire_callback(self, job_id: UUID, callback_url: str) -> None:
        if callback_url.startswith("http://") and not _allow_http_callback():
            await logger.awarning(
                "Skipping HTTP callback for job %s — set LANGFLOW_MCP_JOB_ALLOW_HTTP_CALLBACK=true to allow",
                job_id,
            )
            return
        if not callback_url.startswith(("http://", "https://")):
            await logger.awarning("Skipping callback for job %s — non-HTTP URL", job_id)
            return

        delay = 1.0
        for attempt in range(_CALLBACK_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=_CALLBACK_TIMEOUT_S) as client:
                    response = await client.post(
                        callback_url,
                        json={"job_id": str(job_id)},
                    )
                if response.status_code < _CALLBACK_RETRY_ON_STATUS_BELOW:
                    return
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                await logger.adebug("Callback for job %s attempt %d failed: %s", job_id, attempt + 1, exc)
            await asyncio.sleep(delay)
            delay *= 2

    async def enqueue(
        self,
        *,
        project_id: UUID,
        flow_id: UUID,
        tool_name: str,
        inputs: dict,
        created_by: UUID | None,
        callback_url: str | None = None,
    ) -> MCPJob:
        """Insert a new pending job row. The worker pool will pick it up."""
        now = datetime.now(timezone.utc)
        job = MCPJob(
            project_id=project_id,
            flow_id=flow_id,
            tool_name=tool_name,
            inputs=inputs,
            status=MCPJobStatus.PENDING,
            created_by=created_by,
            callback_url=callback_url,
            created_at=now,
            updated_at=now,
        )
        db = _get_db_service()
        async with db.with_session() as session:
            session.add(job)
            await session.commit()
            await session.refresh(job)
        return job

    async def cancel(self, job_id: UUID) -> bool:
        """Transition pending/running → cancelled. Returns True if a row changed.

        Note: a job currently being executed by a worker will continue running
        until the worker yields; the status flip prevents the worker from
        writing a completed/failed result over the cancellation.
        """
        now = datetime.now(timezone.utc)
        db = _get_db_service()
        async with db.with_session() as session:
            stmt = (
                update(MCPJob)
                .where(
                    MCPJob.id == job_id,
                    MCPJob.status.in_([MCPJobStatus.PENDING, MCPJobStatus.RUNNING]),
                )
                .values(status=MCPJobStatus.CANCELLED, updated_at=now, completed_at=now)
            )
            result = await session.exec(stmt)
            await session.commit()
            return getattr(result, "rowcount", 0) > 0
