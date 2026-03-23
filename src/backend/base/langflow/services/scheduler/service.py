"""Scheduler service for automatic flow execution using APScheduler.

Includes concurrency control (semaphore), jitter (anti-thundering herd),
retry with exponential backoff, and structured observability logging.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from lfx.log.logger import logger

from langflow.services.base import Service
from langflow.services.database.models.schedule.crud import (
    get_all_active_schedules,
    increment_retry_count,
    reset_retry_count,
    update_last_run,
)
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from langflow.services.database.models.schedule.model import FlowSchedule


def _env_int(name: str, default: int) -> int:
    """Read an integer from an environment variable with a fallback default."""
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


class SchedulerService(Service):
    """Service for managing scheduled flow executions via APScheduler.

    Configuration via environment variables:
        LANGFLOW_SCHEDULER_MAX_CONCURRENCY     – max parallel flow executions (default 5)
        LANGFLOW_SCHEDULER_MAX_JITTER_SECONDS  – random delay window in seconds (default 30, 0 to disable)
        LANGFLOW_SCHEDULER_RETRY_BASE_DELAY    – initial retry delay in seconds (default 30)
        LANGFLOW_SCHEDULER_RETRY_MAX_DELAY     – cap for retry delay in seconds (default 300)
        LANGFLOW_SCHEDULER_DEFAULT_MAX_RETRIES – default max retries per schedule (default 3)
    """

    name = "scheduler_service"

    def __init__(self):
        self.scheduler = AsyncIOScheduler()

        # ── Configuration ──────────────────────────────────────────────
        self._max_concurrency: int = _env_int("LANGFLOW_SCHEDULER_MAX_CONCURRENCY", 5)
        self._max_jitter: int = _env_int("LANGFLOW_SCHEDULER_MAX_JITTER_SECONDS", 30)
        self._retry_base_delay: int = _env_int("LANGFLOW_SCHEDULER_RETRY_BASE_DELAY", 30)
        self._retry_max_delay: int = _env_int("LANGFLOW_SCHEDULER_RETRY_MAX_DELAY", 300)
        self._default_max_retries: int = _env_int("LANGFLOW_SCHEDULER_DEFAULT_MAX_RETRIES", 3)

        # ── Observability counters ─────────────────────────────────────
        self._active_count: int = 0
        self._total_executions: int = 0
        self._total_failures: int = 0

        # Semaphore is created lazily in start() to ensure the event loop exists.
        self._semaphore: asyncio.Semaphore | None = None

        self.set_ready()

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the scheduler and load active schedules from DB."""
        await logger.ainfo("Starting SchedulerService...")

        # Create the semaphore inside the running event loop.
        self._semaphore = asyncio.Semaphore(self._max_concurrency)

        await logger.ainfo(
            "SchedulerService configuration",
            extra={
                "max_concurrency": self._max_concurrency,
                "max_jitter_seconds": self._max_jitter,
                "retry_base_delay": self._retry_base_delay,
                "retry_max_delay": self._retry_max_delay,
                "default_max_retries": self._default_max_retries,
            },
        )

        self.scheduler.start()
        await self._load_schedules_from_db()
        await logger.ainfo("SchedulerService started successfully")

    async def teardown(self) -> None:
        """Shutdown the scheduler."""
        await logger.ainfo("Shutting down SchedulerService...")
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await logger.ainfo(
            "SchedulerService shut down",
            extra={
                "total_executions": self._total_executions,
                "total_failures": self._total_failures,
            },
        )

    # ── Schedule management ────────────────────────────────────────────

    async def _load_schedules_from_db(self) -> None:
        """Load all active schedules from the database and register them."""
        try:
            async with session_scope() as session:
                schedules = await get_all_active_schedules(session)
                count = 0
                for schedule in schedules:
                    self.add_schedule(schedule)
                    count += 1
                await logger.ainfo(f"Loaded {count} active schedules from database")
        except Exception:
            await logger.aexception("Failed to load schedules from database")

    def add_schedule(self, schedule: FlowSchedule) -> None:
        """Add or replace a schedule in APScheduler."""
        job_id = f"schedule_{schedule.flow_id}"

        # Remove existing job if present
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)

        trigger = CronTrigger(
            minute=schedule.minute,
            hour=schedule.hour,
            day_of_week=schedule.day_of_week,
            day=schedule.day_of_month,
            month=schedule.month,
            timezone=schedule.timezone,
            start_date=schedule.start_at,
        )

        self.scheduler.add_job(
            self._execute_flow,
            trigger=trigger,
            id=job_id,
            args=[schedule.flow_id, schedule.user_id, schedule.id],
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.debug(f"Added schedule job {job_id} for flow {schedule.flow_id}")

    def remove_schedule(self, flow_id: UUID) -> None:
        """Remove a schedule from APScheduler."""
        job_id = f"schedule_{flow_id}"
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)
            logger.debug(f"Removed schedule job {job_id}")

    # ── Flow execution ─────────────────────────────────────────────────

    async def _execute_flow(
        self,
        flow_id: UUID,
        user_id: UUID,
        schedule_id: UUID,
        *,
        is_retry: bool = False,
    ) -> None:
        """Execute a flow as a scheduled job with concurrency control and retry."""
        from lfx.graph.graph.base import Graph

        from langflow.processing.process import run_graph_internal
        from langflow.services.database.models.flow.model import Flow
        from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
        from langflow.services.jobs.service import JobService

        # ── 1. Jitter: spread arrivals to avoid thundering herd ────────
        if self._max_jitter > 0:
            jitter = random.uniform(0, self._max_jitter)  # noqa: S311
            await logger.adebug(
                f"Applying {jitter:.1f}s jitter for flow {flow_id}",
            )
            await asyncio.sleep(jitter)

        # ── 2. Queue: wait for semaphore slot ──────────────────────────
        t_queued = time.monotonic()
        self._total_executions += 1

        await logger.ainfo(
            "Scheduled flow queued for execution",
            extra={
                "flow_id": str(flow_id),
                "schedule_id": str(schedule_id),
                "active_count": self._active_count,
                "is_retry": is_retry,
            },
        )

        assert self._semaphore is not None  # noqa: S101 - guaranteed after start()
        async with self._semaphore:
            t_started = time.monotonic()
            wait_seconds = t_started - t_queued
            self._active_count += 1
            status = "failed"

            try:
                # ── 3. Reset retry count on regular (non-retry) trigger ─
                if not is_retry:
                    try:
                        async with session_scope() as session:
                            await reset_retry_count(session, schedule_id)
                    except Exception:
                        await logger.aexception("Failed to reset retry count")

                # ── 4. Load flow from DB ───────────────────────────────
                async with session_scope() as session:
                    from sqlmodel import select

                    statement = select(Flow).where(Flow.id == flow_id)
                    result = await session.exec(statement)
                    flow = result.first()

                    if flow is None:
                        await logger.aerror(f"Scheduled flow {flow_id} not found, skipping execution")
                        return

                    if flow.data is None:
                        await logger.aerror(f"Scheduled flow {flow_id} has no data, skipping execution")
                        return

                    flow_data = flow.data

                # ── 5. Build graph ─────────────────────────────────────
                graph = Graph.from_payload(
                    flow_data,
                    flow_id=str(flow_id),
                    user_id=str(user_id),
                )

                # ── 6. Create job and execute ──────────────────────────
                job_id = uuid4()
                job_service = JobService()

                async with session_scope() as session:
                    job = Job(
                        job_id=job_id,
                        flow_id=flow_id,
                        status=JobStatus.QUEUED,
                        type=JobType.SCHEDULED,
                        user_id=user_id,
                    )
                    session.add(job)
                    await session.flush()

                await job_service.execute_with_status(
                    job_id,
                    run_graph_internal,
                    graph,
                    str(flow_id),
                )

                # ── 7. Success ─────────────────────────────────────────
                async with session_scope() as session:
                    await update_last_run(session, schedule_id, "completed")
                    await reset_retry_count(session, schedule_id)

                status = "completed"

            except Exception:
                self._total_failures += 1
                await logger.aexception(f"Scheduled execution failed for flow {flow_id}")

                # Update last run and attempt retry
                await self._handle_retry(flow_id, user_id, schedule_id)

            finally:
                self._active_count -= 1
                duration = time.monotonic() - t_started

                await logger.ainfo(
                    "Scheduled flow execution finished",
                    extra={
                        "flow_id": str(flow_id),
                        "schedule_id": str(schedule_id),
                        "status": status,
                        "duration_seconds": round(duration, 2),
                        "wait_seconds": round(wait_seconds, 2),
                        "active_count": self._active_count,
                        "is_retry": is_retry,
                        "total_executions": self._total_executions,
                        "total_failures": self._total_failures,
                    },
                )

    # ── Retry logic ────────────────────────────────────────────────────

    async def _handle_retry(
        self,
        flow_id: UUID,
        user_id: UUID,
        schedule_id: UUID,
    ) -> None:
        """Handle retry logic after a failed execution.

        Increments retry_count, and if below max_retries, schedules a one-shot
        retry with exponential backoff via APScheduler DateTrigger.
        """
        try:
            async with session_scope() as session:
                await update_last_run(session, schedule_id, "failed")
                schedule = await increment_retry_count(session, schedule_id)

                if schedule is None:
                    return

                max_retries = schedule.max_retries or self._default_max_retries

                if schedule.retry_count <= max_retries:
                    delay = min(
                        self._retry_base_delay * (2 ** (schedule.retry_count - 1)),
                        self._retry_max_delay,
                    )
                    run_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                    retry_job_id = f"schedule_{flow_id}_retry_{schedule.retry_count}"

                    self.scheduler.add_job(
                        self._execute_flow,
                        trigger=DateTrigger(run_date=run_at),
                        id=retry_job_id,
                        args=[flow_id, user_id, schedule_id],
                        kwargs={"is_retry": True},
                        replace_existing=True,
                        misfire_grace_time=60,
                    )
                    await logger.ainfo(
                        f"Scheduled retry {schedule.retry_count}/{max_retries} for flow {flow_id} in {delay}s",
                        extra={
                            "flow_id": str(flow_id),
                            "retry_attempt": schedule.retry_count,
                            "max_retries": max_retries,
                            "retry_delay_seconds": delay,
                        },
                    )
                else:
                    await update_last_run(session, schedule_id, "failed_permanent")
                    await logger.aerror(
                        f"Flow {flow_id} exhausted all {max_retries} retries",
                        extra={
                            "flow_id": str(flow_id),
                            "schedule_id": str(schedule_id),
                            "retry_count": schedule.retry_count,
                        },
                    )
        except Exception:
            await logger.aexception("Failed to handle retry logic")
