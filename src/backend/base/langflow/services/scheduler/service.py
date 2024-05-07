from typing import TYPE_CHECKING

from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from langflow.services.base import Service
from langflow.services.scheduler.middleware import SchedulerMiddleware

from .schema import JobModel

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


class SchedulerService(Service):
    name = "scheduler_service"

    def __init__(self, db_service: "DatabaseService"):
        self.db_service = db_service
        engine = self.db_service._create_engine()
        self.scheduler = AsyncScheduler(SQLAlchemyDataStore(engine=engine))

    def add_middleware(self, app: FastAPI):
        app.add_middleware(SchedulerMiddleware, scheduler=self.scheduler)

    async def add_schedule(
        self, func, schedule_id, cron_string, args=None, kwargs=None, misfire_grace_time=None, max_instances=None
    ):
        trigger = CronTrigger.from_crontab(cron_string)
        schedule_id = await self.scheduler.add_schedule(
            func_or_task_id=func,
            trigger=trigger,
            id=schedule_id,
            args=args or [],
            kwargs=kwargs or {},
            misfire_grace_time=misfire_grace_time,
            max_running_jobs=max_instances,
        )
        return schedule_id

    async def remove_schedule(self, schedule_id):
        await self.scheduler.remove_schedule(schedule_id)

    async def get_scheduled_tasks(self):
        jobs = []
        for job in await self.scheduler.get_schedules():
            jobs.append(JobModel.parse_job(job))
        return jobs
        return jobs
        return jobs
