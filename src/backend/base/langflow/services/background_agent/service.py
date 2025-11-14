"""Background Agent Service for managing persistent agent execution."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.background_agent.utils import execute_flow_background
from langflow.services.base import Service
from langflow.services.database.models.background_agent import (
    AgentStatus,
    BackgroundAgent,
    BackgroundAgentExecution,
    TriggerType,
)
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class BackgroundAgentService(Service):
    """Service for managing background agent execution.

    This service handles:
    - Starting and stopping background agents
    - Scheduling agent execution based on triggers
    - Monitoring agent status and execution history
    - Managing agent lifecycle
    """

    name = "background_agent_service"

    def __init__(self, settings_service: SettingsService):
        """Initialize the background agent service.

        Args:
            settings_service: Settings service for configuration
        """
        self.settings_service = settings_service
        self.scheduler: AsyncIOScheduler | None = None
        self._started = False
        self._agent_jobs: dict[str, str] = {}  # agent_id -> job_id mapping
        self.ready = False

    def set_ready(self) -> None:
        """Mark service as ready and start if not already started."""
        if not self._started:
            self.start()
        super().set_ready()

    def start(self) -> None:
        """Start the background agent service and scheduler."""
        if self._started:
            logger.warning("BackgroundAgentService already started")
            return

        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        self._started = True
        logger.info("BackgroundAgentService started with scheduler")

        # Load and start all active agents
        asyncio.create_task(self._load_active_agents())

    async def stop(self) -> None:
        """Stop the background agent service and scheduler."""
        if not self._started:
            return

        if self.scheduler:
            self.scheduler.shutdown(wait=True)
            self.scheduler = None

        self._agent_jobs.clear()
        self._started = False
        await logger.ainfo("BackgroundAgentService stopped")

    async def teardown(self) -> None:
        """Teardown the service."""
        await self.stop()

    async def _load_active_agents(self) -> None:
        """Load and start all active agents from the database."""
        try:
            async with session_scope() as session:
                # Get all enabled agents with ACTIVE status
                stmt = select(BackgroundAgent).where(
                    BackgroundAgent.enabled == True,  # noqa: E712
                    BackgroundAgent.status == AgentStatus.ACTIVE,
                )
                result = await session.exec(stmt)
                agents = result.all()

                for agent in agents:
                    try:
                        await self._schedule_agent(agent)
                        await logger.ainfo(f"Loaded and scheduled agent: {agent.name} (ID: {agent.id})")
                    except (ValueError, RuntimeError) as e:
                        await logger.aerror(f"Failed to schedule agent {agent.id}: {e}")
                    except Exception as e:  # noqa: BLE001
                        await logger.aerror(f"Unexpected error scheduling agent {agent.id}: {e}")
        except (ValueError, RuntimeError) as e:
            await logger.aerror(f"Failed to load active agents: {e}")
        except Exception as e:  # noqa: BLE001
            await logger.aerror(f"Unexpected error loading active agents: {e}")

    async def start_agent(self, agent_id: UUID) -> dict[str, Any]:
        """Start a background agent.

        Args:
            agent_id: UUID of the agent to start

        Returns:
            dict containing status information

        Raises:
            ValueError: If agent not found or scheduler not initialized
        """
        if not self.scheduler:
            msg = "Scheduler not initialized"
            raise ValueError(msg)

        async with session_scope() as session:
            agent = await session.get(BackgroundAgent, agent_id)
            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            # Update agent status
            agent.status = AgentStatus.ACTIVE
            agent.updated_at = datetime.now(timezone.utc)
            session.add(agent)
            await session.commit()
            await session.refresh(agent)

            # Schedule the agent
            await self._schedule_agent(agent)

            await logger.ainfo(f"Started background agent: {agent.name} (ID: {agent_id})")

            return {
                "status": "started",
                "agent_id": str(agent_id),
                "next_run_at": agent.next_run_at.isoformat() if agent.next_run_at else None,
            }

    async def stop_agent(self, agent_id: UUID) -> dict[str, Any]:
        """Stop a background agent.

        Args:
            agent_id: UUID of the agent to stop

        Returns:
            dict containing status information

        Raises:
            ValueError: If agent not found
        """
        agent_id_str = str(agent_id)

        # Remove from scheduler
        if agent_id_str in self._agent_jobs:
            job_id = self._agent_jobs[agent_id_str]
            if self.scheduler:
                self.scheduler.remove_job(job_id)
            del self._agent_jobs[agent_id_str]

        # Update agent status in database
        async with session_scope() as session:
            agent = await session.get(BackgroundAgent, agent_id)
            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            agent.status = AgentStatus.STOPPED
            agent.updated_at = datetime.now(timezone.utc)
            agent.next_run_at = None
            session.add(agent)
            await session.commit()

        await logger.ainfo(f"Stopped background agent: {agent_id}")

        return {"status": "stopped", "agent_id": agent_id_str}

    async def pause_agent(self, agent_id: UUID) -> dict[str, Any]:
        """Pause a background agent.

        Args:
            agent_id: UUID of the agent to pause

        Returns:
            dict containing status information
        """
        agent_id_str = str(agent_id)

        # Pause in scheduler
        if agent_id_str in self._agent_jobs:
            job_id = self._agent_jobs[agent_id_str]
            if self.scheduler:
                self.scheduler.pause_job(job_id)

        # Update agent status in database
        async with session_scope() as session:
            agent = await session.get(BackgroundAgent, agent_id)
            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            agent.status = AgentStatus.PAUSED
            agent.updated_at = datetime.now(timezone.utc)
            session.add(agent)
            await session.commit()

        await logger.ainfo(f"Paused background agent: {agent_id}")

        return {"status": "paused", "agent_id": agent_id_str}

    async def resume_agent(self, agent_id: UUID) -> dict[str, Any]:
        """Resume a paused background agent.

        Args:
            agent_id: UUID of the agent to resume

        Returns:
            dict containing status information
        """
        agent_id_str = str(agent_id)

        # Resume in scheduler
        if agent_id_str in self._agent_jobs:
            job_id = self._agent_jobs[agent_id_str]
            if self.scheduler:
                self.scheduler.resume_job(job_id)

        # Update agent status in database
        async with session_scope() as session:
            agent = await session.get(BackgroundAgent, agent_id)
            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            agent.status = AgentStatus.ACTIVE
            agent.updated_at = datetime.now(timezone.utc)
            session.add(agent)
            await session.commit()

        await logger.ainfo(f"Resumed background agent: {agent_id}")

        return {"status": "active", "agent_id": agent_id_str}

    async def trigger_agent(self, agent_id: UUID, trigger_source: str = "manual") -> dict[str, Any]:
        """Manually trigger a background agent execution.

        Args:
            agent_id: UUID of the agent to trigger
            trigger_source: Source of the trigger (default: "manual")

        Returns:
            dict containing execution information
        """
        async with session_scope() as session:
            agent = await session.get(BackgroundAgent, agent_id)
            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            # Create execution record
            execution = BackgroundAgentExecution(
                agent_id=agent_id,
                trigger_source=trigger_source,
                status="RUNNING",
            )
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
            execution_id = execution.id

        # Execute in background
        asyncio.create_task(self._execute_agent_job(agent_id, execution_id, trigger_source))

        return {
            "status": "triggered",
            "agent_id": str(agent_id),
            "execution_id": str(execution_id),
        }

    async def _schedule_agent(self, agent: BackgroundAgent) -> None:
        """Schedule an agent based on its trigger configuration.

        Args:
            agent: The agent to schedule
        """
        if not self.scheduler:
            msg = "Scheduler not initialized"
            raise ValueError(msg)

        agent_id_str = str(agent.id)

        # Remove existing job if any
        if agent_id_str in self._agent_jobs:
            job_id = self._agent_jobs[agent_id_str]
            self.scheduler.remove_job(job_id)

        # Create appropriate trigger based on type
        trigger = self._create_trigger(agent.trigger_type, agent.trigger_config)

        if trigger is None:
            # For webhook/event triggers, no scheduling needed
            await logger.ainfo(f"Agent {agent.name} uses {agent.trigger_type} trigger - no scheduling required")
            return

        # Add job to scheduler
        job = self.scheduler.add_job(
            self._execute_agent,
            trigger=trigger,
            args=[agent.id],
            id=agent_id_str,
            name=f"background_agent_{agent.name}",
            replace_existing=True,
        )

        self._agent_jobs[agent_id_str] = job.id

        # Update next_run_at
        if job.next_run_time:
            async with session_scope() as session:
                db_agent = await session.get(BackgroundAgent, agent.id)
                if db_agent:
                    db_agent.next_run_at = job.next_run_time
                    session.add(db_agent)
                    await session.commit()

        await logger.ainfo(f"Scheduled agent {agent.name} with {agent.trigger_type} trigger")

    def _create_trigger(self, trigger_type: TriggerType, trigger_config: dict) -> Any:
        """Create an APScheduler trigger based on type and configuration.

        Args:
            trigger_type: Type of trigger
            trigger_config: Configuration for the trigger

        Returns:
            APScheduler trigger instance or None for webhook/event triggers
        """
        if trigger_type == TriggerType.CRON:
            # Cron trigger expects: minute, hour, day, month, day_of_week
            return CronTrigger(
                minute=trigger_config.get("minute", "*"),
                hour=trigger_config.get("hour", "*"),
                day=trigger_config.get("day", "*"),
                month=trigger_config.get("month", "*"),
                day_of_week=trigger_config.get("day_of_week", "*"),
            )
        elif trigger_type == TriggerType.INTERVAL:
            # Interval trigger expects seconds, minutes, hours, days, weeks
            return IntervalTrigger(
                seconds=trigger_config.get("seconds", 0),
                minutes=trigger_config.get("minutes", 0),
                hours=trigger_config.get("hours", 0),
                days=trigger_config.get("days", 0),
                weeks=trigger_config.get("weeks", 0),
            )
        elif trigger_type == TriggerType.DATE:
            # Date trigger expects a specific datetime
            run_date = trigger_config.get("run_date")
            if run_date:
                if isinstance(run_date, str):
                    run_date = datetime.fromisoformat(run_date)
                return DateTrigger(run_date=run_date)
        elif trigger_type in (TriggerType.WEBHOOK, TriggerType.EVENT):
            # These triggers are handled by API endpoints or event listeners
            return None

        msg = f"Unsupported trigger type: {trigger_type}"
        raise ValueError(msg)

    async def _execute_agent(self, agent_id: UUID) -> None:
        """Execute an agent (called by scheduler).

        Args:
            agent_id: UUID of the agent to execute
        """
        # Create execution record
        async with session_scope() as session:
            execution = BackgroundAgentExecution(
                agent_id=agent_id,
                trigger_source="scheduled",
                status="RUNNING",
            )
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
            execution_id = execution.id

        # Execute in background task
        await self._execute_agent_job(agent_id, execution_id, "scheduled")

    async def _execute_agent_job(self, agent_id: UUID, execution_id: UUID, trigger_source: str) -> None:
        """Execute the actual agent job.

        Args:
            agent_id: UUID of the agent
            execution_id: UUID of the execution record
            trigger_source: Source of the trigger
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Get agent configuration
            async with session_scope() as session:
                agent = await session.get(BackgroundAgent, agent_id)
                if not agent:
                    msg = f"Agent {agent_id} not found"
                    raise ValueError(msg)

                flow_id = agent.flow_id
                user_id = agent.user_id
                input_config = agent.input_config

            # Execute the flow
            result = await execute_flow_background(
                flow_id=flow_id,
                user_id=user_id,
                input_config=input_config,
            )

            # Update execution record as success
            async with session_scope() as session:
                execution = await session.get(BackgroundAgentExecution, execution_id)
                if execution:
                    execution.status = "SUCCESS"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.result = result
                    session.add(execution)
                    await session.commit()

                # Update agent last_run_at
                agent = await session.get(BackgroundAgent, agent_id)
                if agent:
                    agent.last_run_at = start_time
                    # Update next_run_at from scheduler
                    if str(agent_id) in self._agent_jobs and self.scheduler:
                        job = self.scheduler.get_job(self._agent_jobs[str(agent_id)])
                        if job and job.next_run_time:
                            agent.next_run_at = job.next_run_time
                    session.add(agent)
                    await session.commit()

            await logger.ainfo(f"Successfully executed agent {agent_id} (execution: {execution_id})")

        except Exception as e:  # noqa: BLE001
            error_message = str(e)
            await logger.aerror(f"Failed to execute agent {agent_id}: {error_message}")

            # Update execution record as failed
            async with session_scope() as session:
                execution = await session.get(BackgroundAgentExecution, execution_id)
                if execution:
                    execution.status = "FAILED"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.error_message = error_message
                    session.add(execution)
                    await session.commit()

                # Update agent status to ERROR
                agent = await session.get(BackgroundAgent, agent_id)
                if agent:
                    agent.status = AgentStatus.ERROR
                    agent.last_run_at = start_time
                    session.add(agent)
                    await session.commit()

    async def get_agent_status(self, agent_id: UUID) -> dict[str, Any]:
        """Get the status of a background agent.

        Args:
            agent_id: UUID of the agent

        Returns:
            dict containing agent status information
        """
        async with session_scope() as session:
            agent = await session.get(BackgroundAgent, agent_id)
            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            # Get scheduler info if available
            next_run = None
            if str(agent_id) in self._agent_jobs and self.scheduler:
                job = self.scheduler.get_job(self._agent_jobs[str(agent_id)])
                if job and job.next_run_time:
                    next_run = job.next_run_time.isoformat()

            return {
                "agent_id": str(agent.id),
                "name": agent.name,
                "status": agent.status.value,
                "enabled": agent.enabled,
                "last_run_at": agent.last_run_at.isoformat() if agent.last_run_at else None,
                "next_run_at": next_run or (agent.next_run_at.isoformat() if agent.next_run_at else None),
                "trigger_type": agent.trigger_type.value,
            }

    async def get_agent_executions(
        self, agent_id: UUID, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get execution history for an agent.

        Args:
            agent_id: UUID of the agent
            limit: Maximum number of executions to return
            offset: Number of executions to skip

        Returns:
            list of execution records
        """
        async with session_scope() as session:
            stmt = (
                select(BackgroundAgentExecution)
                .where(BackgroundAgentExecution.agent_id == agent_id)
                .order_by(BackgroundAgentExecution.started_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.exec(stmt)
            executions = result.all()

            return [
                {
                    "execution_id": str(exec.id),
                    "started_at": exec.started_at.isoformat(),
                    "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
                    "status": exec.status,
                    "trigger_source": exec.trigger_source,
                    "error_message": exec.error_message,
                }
                for exec in executions
            ]
