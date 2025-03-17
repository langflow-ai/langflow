"""Scheduler service for Langflow using APScheduler."""
import logging
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from langflow.services.base import Service
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.scheduler import Scheduler, SchedulerCreate, SchedulerRead, SchedulerUpdate
from langflow.services.deps import get_session, get_settings_service
from langflow.services.schema import ServiceType

logger = logging.getLogger(__name__)


class SchedulerService(Service):
    """Service for managing scheduled tasks."""

    name = ServiceType.SCHEDULER_SERVICE

    def __init__(self):
        """Initialize the scheduler service."""
        super().__init__()
        self.scheduler = AsyncIOScheduler()
        self.tasks: dict[str, str] = {}  # Map scheduler_id to job_id
        self.running = False

    def set_ready(self):
        """Set the service as ready."""
        self._ready = True

    async def teardown(self):
        """Teardown the service."""
        await self.stop()

    async def start(self):
        """Start the scheduler."""
        if not self.running:
            self.running = True
            self.scheduler.start()
            logger.info("Scheduler service started")

    async def stop(self):
        """Stop the scheduler."""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Scheduler service stopped")

    async def create_scheduler(
        self, *, session: AsyncSession, scheduler: SchedulerCreate
    ) -> SchedulerRead:
        """Create a new scheduler."""
        # Check if flow exists
        flow_query = select(Flow).where(Flow.id == scheduler.flow_id)
        flow = await session.exec(flow_query)
        flow = flow.first()
        if not flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flow with id {scheduler.flow_id} not found",
            )

        # Create scheduler in DB
        db_scheduler = Scheduler.model_validate(scheduler)
        session.add(db_scheduler)
        await session.commit()
        await session.refresh(db_scheduler)

        # Create job in scheduler
        await self._create_job(db_scheduler)

        return SchedulerRead.model_validate(db_scheduler)

    async def get_scheduler(
        self, *, session: AsyncSession, scheduler_id: UUID
    ) -> SchedulerRead:
        """Get a scheduler by ID."""
        scheduler_query = select(Scheduler).where(Scheduler.id == scheduler_id)
        scheduler = await session.exec(scheduler_query)
        scheduler = scheduler.first()
        if not scheduler:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduler with id {scheduler_id} not found",
            )
        return SchedulerRead.model_validate(scheduler)

    async def get_schedulers(
        self, *, session: AsyncSession, flow_id: UUID | None = None
    ) -> list[SchedulerRead]:
        """Get all schedulers, optionally filtered by flow_id."""
        if flow_id:
            scheduler_query = select(Scheduler).where(Scheduler.flow_id == flow_id)
        else:
            scheduler_query = select(Scheduler)

        schedulers = await session.exec(scheduler_query)
        schedulers = schedulers.all()
        return [SchedulerRead.model_validate(scheduler) for scheduler in schedulers]

    async def update_scheduler(
        self, *, session: AsyncSession, scheduler_id: UUID, scheduler: SchedulerUpdate
    ) -> SchedulerRead:
        """Update a scheduler."""
        scheduler_query = select(Scheduler).where(Scheduler.id == scheduler_id)
        db_scheduler = await session.exec(scheduler_query)
        db_scheduler = db_scheduler.first()
        if not db_scheduler:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduler with id {scheduler_id} not found",
            )

        # Update scheduler in DB
        scheduler_data = scheduler.model_dump(exclude_unset=True)
        for key, value in scheduler_data.items():
            setattr(db_scheduler, key, value)

        # If enabled status changed, update the job
        if "enabled" in scheduler_data:
            if scheduler_data["enabled"] and not db_scheduler.enabled:
                # Enable the job
                await self._create_job(db_scheduler)
            elif not scheduler_data["enabled"] and db_scheduler.enabled:
                # Disable the job
                await self._delete_job(db_scheduler.id)

        # If schedule changed, recreate the job
        if "cron_expression" in scheduler_data or "interval_seconds" in scheduler_data:
            # Delete old job if exists
            await self._delete_job(db_scheduler.id)
            # Create new job if enabled
            if db_scheduler.enabled:
                await self._create_job(db_scheduler)

        await session.commit()
        await session.refresh(db_scheduler)
        return SchedulerRead.model_validate(db_scheduler)

    async def delete_scheduler(
        self, *, session: AsyncSession, scheduler_id: UUID
    ) -> None:
        """Delete a scheduler."""
        scheduler_query = select(Scheduler).where(Scheduler.id == scheduler_id)
        scheduler = await session.exec(scheduler_query)
        scheduler = scheduler.first()
        if not scheduler:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduler with id {scheduler_id} not found",
            )

        # Delete job from scheduler
        await self._delete_job(scheduler_id)

        # Delete scheduler from DB
        await session.delete(scheduler)
        await session.commit()

    async def _create_job(self, scheduler: Scheduler) -> None:
        """Create a job in the scheduler."""
        # Delete existing job if it exists
        await self._delete_job(scheduler.id)

        # Create trigger based on scheduler type
        if scheduler.cron_expression:
            trigger = CronTrigger.from_crontab(scheduler.cron_expression)
        else:
            # Use interval_seconds (which now has a default value of 60)
            trigger = IntervalTrigger(seconds=scheduler.interval_seconds)

        # Define the job function
        async def run_flow():
            """Run the flow."""
            logger.info(f"Running scheduled flow {scheduler.flow_id}")
            try:
                # Import necessary modules
                import httpx
                from langflow.services.deps import get_settings_service
                
                # Get the Langflow port from settings
                settings = get_settings_service().settings
                port = settings.port
                host = "localhost"  # Using localhost since this is running on the same machine
                
                # Construct the URL for the run endpoint
                url = f"http://{host}:{port}/api/v1/run/{scheduler.flow_id}"
                
                # Prepare the request payload
                payload = {
                    "inputs": None,  # No specific inputs for scheduled runs
                    "stream": False  # No streaming for scheduled runs
                }
                
                # Make the HTTP request to run the flow
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload)
                    
                    if response.status_code == 200:
                        logger.info(f"Successfully ran scheduled flow {scheduler.flow_id}")
                    else:
                        logger.error(f"Error running flow: HTTP {response.status_code} - {response.text}")
                        
            except Exception as e:
                logger.error(f"Error running scheduled flow {scheduler.flow_id}: {e}", exc_info=True)

        # Add the job to the scheduler
        job = self.scheduler.add_job(
            run_flow,
            trigger=trigger,
            id=str(scheduler.id),
            replace_existing=True
        )

        # Store job ID
        self.tasks[str(scheduler.id)] = job.id

    async def _delete_job(self, scheduler_id: UUID) -> None:
        """Delete a job from the scheduler."""
        job_id = self.tasks.get(str(scheduler_id))
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
            except Exception as e:
                logger.error(f"Error removing job {job_id}: {e}")
            # Remove from tasks dict
            del self.tasks[str(scheduler_id)]


# Create a global instance of the scheduler service
scheduler_service = SchedulerService()
