"""Scheduler service for executing flows on a cron schedule.

Uses croniter for cron expression parsing and asyncio for task scheduling.
"""

from __future__ import annotations

import asyncio
import zoneinfo
from datetime import datetime, timezone
from uuid import UUID

from croniter import croniter
from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.base import Service
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_schedule.model import FlowSchedule
from langflow.services.deps import session_scope


class SchedulerService(Service):
    """Service that manages scheduled flow executions using cron expressions."""

    name = "scheduler_service"

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}  # schedule_id -> task
        self._monitor_task: asyncio.Task | None = None
        self._running = False
        self.set_ready()

    async def start(self) -> None:
        """Start the scheduler: load all active schedules and begin monitoring."""
        if self._running:
            return
        self._running = True
        await logger.ainfo("Starting scheduler service...")
        await self._load_schedules()
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        await logger.ainfo("Scheduler service started")

    async def stop(self) -> None:
        """Stop all scheduled tasks and the monitor loop."""
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        await logger.ainfo("Scheduler service stopped")

    async def teardown(self) -> None:
        await self.stop()

    async def _load_schedules(self) -> None:
        """Load all active schedules from the database and start their tasks."""
        try:
            async with session_scope() as session:
                result = await session.exec(
                    select(FlowSchedule).where(FlowSchedule.is_active == True)  # noqa: E712
                )
                schedules = result.all()
                for schedule in schedules:
                    self._start_schedule_task(schedule.id, schedule.flow_id, schedule.cron_expression, schedule.timezone)
                await logger.ainfo(f"Loaded {len(schedules)} active schedule(s)")
        except Exception:
            await logger.aexception("Failed to load schedules from database")

    async def _monitor_loop(self) -> None:
        """Periodically reload schedules to pick up changes (every 60s)."""
        while self._running:
            try:
                await asyncio.sleep(60)
                await self._sync_schedules()
            except asyncio.CancelledError:
                break
            except Exception:
                await logger.aexception("Error in scheduler monitor loop")

    async def _sync_schedules(self) -> None:
        """Sync running tasks with active schedules in the database."""
        try:
            async with session_scope() as session:
                result = await session.exec(
                    select(FlowSchedule).where(FlowSchedule.is_active == True)  # noqa: E712
                )
                active_schedules = {str(s.id): s for s in result.all()}

            # Stop tasks for schedules that were deactivated or deleted
            to_remove = [sid for sid in self._tasks if sid not in active_schedules]
            for sid in to_remove:
                task = self._tasks.pop(sid)
                if not task.done():
                    task.cancel()

            # Start tasks for new active schedules
            for sid, schedule in active_schedules.items():
                if sid not in self._tasks or self._tasks[sid].done():
                    self._start_schedule_task(
                        schedule.id, schedule.flow_id, schedule.cron_expression, schedule.timezone
                    )
        except Exception:
            await logger.aexception("Error syncing schedules")

    def _start_schedule_task(
        self, schedule_id: UUID, flow_id: UUID, cron_expression: str, tz: str
    ) -> None:
        """Start an asyncio task that waits for cron triggers and executes the flow."""
        sid = str(schedule_id)
        if sid in self._tasks and not self._tasks[sid].done():
            self._tasks[sid].cancel()
        self._tasks[sid] = asyncio.create_task(
            self._cron_runner(schedule_id, flow_id, cron_expression, tz)
        )

    async def _cron_runner(
        self, schedule_id: UUID, flow_id: UUID, cron_expression: str, tz: str
    ) -> None:
        """Run loop: sleep until the next cron trigger, then execute the flow."""
        try:
            tzinfo = zoneinfo.ZoneInfo(tz)
        except Exception:
            await logger.aerror(f"Invalid timezone '{tz}' for schedule {schedule_id}, using UTC")
            tzinfo = timezone.utc

        while self._running:
            try:
                now = datetime.now(tzinfo)
                cron = croniter(cron_expression, now)
                next_run = cron.get_next(datetime)

                # Update next_run_at in database
                await self._update_next_run(schedule_id, next_run)

                # Sleep until next execution
                delay = (next_run - now).total_seconds()
                if delay > 0:
                    await asyncio.sleep(delay)

                if not self._running:
                    break

                # Execute the flow
                await self._execute_flow(schedule_id, flow_id)

            except asyncio.CancelledError:
                break
            except Exception:
                await logger.aexception(f"Error in cron runner for schedule {schedule_id}")
                # Wait before retrying to avoid tight error loops
                await asyncio.sleep(30)

    async def _execute_flow(self, schedule_id: UUID, flow_id: UUID) -> None:
        """Execute a flow and update the schedule's run status."""
        from langflow.api.v1.endpoints import simple_run_flow
        from langflow.api.v1.schemas import SimplifiedAPIRequest

        await logger.ainfo(f"Executing scheduled flow {flow_id} (schedule: {schedule_id})")
        try:
            async with session_scope() as session:
                flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
                if not flow:
                    await self._update_run_status(schedule_id, "failed", error=f"Flow {flow_id} not found")
                    return

                input_request = SimplifiedAPIRequest(input_value="", input_type="chat", output_type="any")
                result = await simple_run_flow(flow, input_request)
                await self._update_run_status(schedule_id, "completed")
                await logger.ainfo(f"Scheduled flow {flow_id} completed successfully")

        except Exception as e:
            error_msg = str(e)[:500]
            await logger.aerror(f"Scheduled flow {flow_id} failed: {error_msg}")
            await self._update_run_status(schedule_id, "failed", error=error_msg)

    async def _update_next_run(self, schedule_id: UUID, next_run: datetime) -> None:
        """Update the next_run_at field for a schedule."""
        try:
            async with session_scope() as session:
                schedule = (
                    await session.exec(select(FlowSchedule).where(FlowSchedule.id == schedule_id))
                ).first()
                if schedule:
                    schedule.next_run_at = next_run
                    session.add(schedule)
        except Exception:
            await logger.aexception(f"Failed to update next_run for schedule {schedule_id}")

    async def _update_run_status(self, schedule_id: UUID, status: str, *, error: str | None = None) -> None:
        """Update the last run status/time for a schedule."""
        try:
            async with session_scope() as session:
                schedule = (
                    await session.exec(select(FlowSchedule).where(FlowSchedule.id == schedule_id))
                ).first()
                if schedule:
                    schedule.last_run_at = datetime.now(timezone.utc)
                    schedule.last_run_status = status
                    schedule.last_run_error = error
                    schedule.updated_at = datetime.now(timezone.utc)
                    session.add(schedule)
        except Exception:
            await logger.aexception(f"Failed to update run status for schedule {schedule_id}")

    # --- Public API for managing schedules at runtime ---

    async def add_schedule(self, schedule: FlowSchedule) -> None:
        """Add and start a new schedule."""
        if schedule.is_active:
            self._start_schedule_task(schedule.id, schedule.flow_id, schedule.cron_expression, schedule.timezone)

    async def remove_schedule(self, schedule_id: UUID) -> None:
        """Stop and remove a schedule."""
        sid = str(schedule_id)
        task = self._tasks.pop(sid, None)
        if task and not task.done():
            task.cancel()

    async def update_schedule(self, schedule: FlowSchedule) -> None:
        """Update a schedule: restart its task if active, or stop it if inactive."""
        await self.remove_schedule(schedule.id)
        if schedule.is_active:
            self._start_schedule_task(schedule.id, schedule.flow_id, schedule.cron_expression, schedule.timezone)
