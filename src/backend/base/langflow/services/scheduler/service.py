"""Scheduler service for Langflow using APScheduler."""
import logging
from uuid import UUID
import asyncio
import time

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
            
            # Log the number of scheduled jobs
            jobs = self.scheduler.get_jobs()
            if jobs:
                logger.info(f"Loaded {len(jobs)} scheduled jobs")
                for job in jobs:
                    next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Not scheduled"
                    logger.info(f"Job {job.id} next run: {next_run}")
            else:
                logger.info("No scheduled jobs found")

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
            schedule_desc = f"cron expression '{scheduler.cron_expression}'"
        else:
            # Use interval_seconds (which now has a default value of 60)
            trigger = IntervalTrigger(seconds=scheduler.interval_seconds)
            schedule_desc = f"interval of {scheduler.interval_seconds} seconds"

        # Log job creation
        logger.info(f"Creating scheduled job for flow_id={scheduler.flow_id} with {schedule_desc} (scheduler_id={scheduler.id})")

        # Define the job function
        async def run_flow():
            """Run the flow."""
            start_time = None
            try:
                # Import necessary modules
                import httpx
                import time
                import json
                from langflow.services.deps import get_settings_service
                
                # Log when the scheduled flow starts running
                start_time = time.time()
                logger.info(f"Starting scheduled flow execution for flow_id={scheduler.flow_id} (scheduler_id={scheduler.id})")
                
                # Log job configuration
                job = self.scheduler.get_job(str(scheduler.id))
                if job:
                    logger.info(f"Job configuration: max_instances={job.max_instances}, next_run_time={job.next_run_time}")
                
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
                
                logger.warning(f"[BUG LOG] Attempting to execute flow with payload: {payload}")
                
                # Make the HTTP request to run the flow with a timeout from settings and retry logic
                # Using the scheduler_timeout setting which defaults to 300 seconds (5 minutes)
                max_retries = 3
                retry_delay = 5
                
                for attempt in range(1, max_retries + 1):
                    try:
                        logger.warning(f"[BUG LOG] Attempt {attempt}/{max_retries} to run scheduled flow {scheduler.flow_id}")
                        async with httpx.AsyncClient(timeout=settings.scheduler_timeout) as client:
                            logger.warning(f"[BUG LOG] Sending POST request to {url}")
                            response = await client.post(url, json=payload)
                            
                            if response.status_code == 200:
                                elapsed_time = time.time() - start_time
                                # Log more detailed execution results
                                try:
                                    result_data = response.json()
                                    logger.warning(f"[BUG LOG] Successfully ran scheduled flow {scheduler.flow_id} in {elapsed_time:.2f} seconds")
                                    logger.warning(f"[BUG LOG] Flow execution result: {json.dumps(result_data, indent=2)}")
                                    
                                    # Extract and log specific parts of the result for easier debugging
                                    if isinstance(result_data, dict):
                                        if 'result' in result_data:
                                            logger.warning(f"[BUG LOG] Flow result content: {result_data['result']}")
                                        if 'error' in result_data:
                                            logger.warning(f"[BUG LOG] Flow execution error: {result_data['error']}")
                                    
                                    return
                                except Exception as e:
                                    logger.warning(f"[BUG LOG] Error parsing flow execution result: {e}")
                                    logger.warning(f"[BUG LOG] Raw response: {response.text[:1000]}...")
                                return
                            else:
                                logger.warning(f"[BUG LOG] Error running flow: HTTP {response.status_code} - {response.text}")
                                if attempt < max_retries:
                                    logger.warning(f"[BUG LOG] Retrying in {retry_delay} seconds...")
                                    await asyncio.sleep(retry_delay)
                                else:
                                    logger.warning(f"[BUG LOG] Failed to run scheduled flow after {max_retries} attempts")
                    except httpx.ReadTimeout:
                        elapsed_time = time.time() - start_time
                        logger.warning(f"[BUG LOG] Timeout running scheduled flow {scheduler.flow_id} after {elapsed_time:.2f} seconds")
                        if attempt < max_retries:
                            logger.warning(f"[BUG LOG] Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.warning(f"[BUG LOG] Failed to run scheduled flow after {max_retries} attempts due to timeout")
                    except Exception as e:
                        logger.warning(f"[BUG LOG] Error on attempt {attempt}/{max_retries} running scheduled flow {scheduler.flow_id}: {e}", exc_info=True)
                        if attempt < max_retries:
                            logger.warning(f"[BUG LOG] Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.warning(f"[BUG LOG] Failed to run scheduled flow after {max_retries} attempts")
                
            except Exception as e:
                elapsed_time = None
                if start_time:
                    import time
                    elapsed_time = time.time() - start_time
                    elapsed_str = f" after {elapsed_time:.2f} seconds"
                else:
                    elapsed_str = ""
                logger.warning(f"[BUG LOG] Error running scheduled flow {scheduler.flow_id}{elapsed_str}: {e}", exc_info=True)

        # Add the job to the scheduler with max_instances=5 to allow more instances
        job = self.scheduler.add_job(
            run_flow,
            trigger=trigger,
            id=str(scheduler.id),
            replace_existing=True,
            max_instances=5,  # Allow up to 5 instances to run concurrently
            coalesce=True,   # Coalesce missed executions to prevent pile-up
            misfire_grace_time=300  # Allow misfires up to 5 minutes late
        )

        # Store job ID
        self.tasks[str(scheduler.id)] = job.id
        
        # Log job scheduling details
        next_run_time = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Not scheduled"
        logger.info(f"Scheduled job for flow_id={scheduler.flow_id} created successfully. Next run time: {next_run_time}")

    async def _delete_job(self, scheduler_id: UUID) -> None:
        """Delete a job from the scheduler."""
        job_id = self.tasks.get(str(scheduler_id))
        if job_id:
            try:
                # Get job info before removing
                job = self.scheduler.get_job(job_id)
                if job:
                    next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Not scheduled"
                    logger.info(f"Removing scheduled job {job_id} for scheduler_id={scheduler_id}. Next run was: {next_run}")
                
                self.scheduler.remove_job(job_id)
                logger.info(f"Successfully removed job {job_id} for scheduler_id={scheduler_id}")
            except Exception as e:
                logger.error(f"Error removing job {job_id} for scheduler_id={scheduler_id}: {e}")
            # Remove from tasks dict
            del self.tasks[str(scheduler_id)]
        else:
            logger.debug(f"No job found for scheduler_id={scheduler_id}")

    def get_job_info(self, scheduler_id: UUID) -> dict:
        """Get information about a scheduled job."""
        job_id = self.tasks.get(str(scheduler_id))
        if not job_id:
            return {"status": "not_found", "message": f"No job found for scheduler_id={scheduler_id}"}
        
        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                return {"status": "not_found", "message": f"Job {job_id} not found in scheduler"}
            
            return {
                "status": "scheduled" if job.next_run_time else "paused",
                "job_id": job_id,
                "next_run_time": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
        except Exception as e:
            logger.error(f"Error getting job info for {job_id}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_scheduler_status(self) -> dict:
        """Get the status of the scheduler service and all scheduled jobs."""
        jobs = self.scheduler.get_jobs()
        job_statuses = []
        
        for job in jobs:
            scheduler_id = job.id
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Not scheduled"
            
            job_statuses.append({
                "scheduler_id": scheduler_id,
                "status": "scheduled" if job.next_run_time else "paused",
                "next_run_time": next_run,
                "trigger": str(job.trigger),
            })
        
        return {
            "service_status": "running" if self.running else "stopped",
            "job_count": len(jobs),
            "jobs": job_statuses
        }

    async def get_next_run_times(self, *, session: AsyncSession, flow_id: UUID | None = None) -> list[dict]:
        """Get the next run times for all scheduled jobs, optionally filtered by flow_id."""
        # Get schedulers from database
        if flow_id:
            scheduler_query = select(Scheduler).where(Scheduler.flow_id == flow_id)
        else:
            scheduler_query = select(Scheduler)
        
        schedulers = await session.exec(scheduler_query)
        schedulers = schedulers.all()
        
        result = []
        for scheduler in schedulers:
            job_info = self.get_job_info(scheduler.id)
            result.append({
                "scheduler_id": str(scheduler.id),
                "flow_id": str(scheduler.flow_id),
                "enabled": scheduler.enabled,
                "next_run_time": job_info.get("next_run_time"),
                "status": job_info.get("status"),
                "schedule_type": "cron" if scheduler.cron_expression else "interval",
                "schedule": scheduler.cron_expression if scheduler.cron_expression else f"{scheduler.interval_seconds} seconds",
            })
        
        return result


# Create a global instance of the scheduler service
scheduler_service = SchedulerService()
