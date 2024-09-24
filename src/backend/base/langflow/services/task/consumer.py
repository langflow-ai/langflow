import asyncio
from typing import TYPE_CHECKING

from langflow.services.deps import get_task_orchestration_service

if TYPE_CHECKING:
    from langflow.services.task_orchestration.service import TaskOrchestrationService


async def consume_tasks(should_stop: bool):
    task_orchestration_service: "TaskOrchestrationService" = get_task_orchestration_service()
    while not should_stop:
        notifications = task_orchestration_service.get_notifications()
        for notification in notifications:
            if notification.event_type == "task_created":
                task = task_orchestration_service.get_task(notification.task_id)
                task_orchestration_service.consume_task(task.id)
        await asyncio.sleep(1)


class TaskConsumer:
    def __init__(self):
        self.should_stop = False
        self.task = None

    async def start(self):
        self.task = asyncio.create_task(self.run())

    async def stop(self):
        self.should_stop = True
        if self.task:
            await self.task

    async def run(self):
        while not self.should_stop:
            await consume_tasks(self.should_stop)


task_consumer = TaskConsumer()
