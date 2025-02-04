import asyncio
from collections.abc import Callable

from celery import shared_task
from loguru import logger
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_task_orchestration_service
from langflow.worker import simple_run_flow_task_celery


@shared_task
def consume_task_celery(task_id: str):
    """Celery task to consume a task by its task_id.

    This task is triggered when a new task is created.

    In production, the async `consume_task` method is executed using
    asgiref's async_to_sync helper. However, when running in eager/test
    mode (where an event loop is already running) we run the coroutine
    in a separate thread that gets its own event loop.
    """
    service = get_task_orchestration_service()
    from langflow.core.celery_app import celery_app  # Adjust import based on your project setup

    if celery_app.conf.task_always_eager:
        # Running in eager mode (for example in tests) where an event loop is already active.
        # Run the async function in a separate thread to bypass the "cannot nest event loops" error.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_consume_task, service, task_id)
            return future.result()
    else:
        # In a normal (non-eager) Celery worker, there is no active event loop on the thread,
        # so we can use async_to_sync safely.
        from asgiref.sync import async_to_sync

        return async_to_sync(service.consume_task)(task_id)


def _run_consume_task(service, task_id):
    """Helper function to run the async consume_task method in a separate event loop."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(service.consume_task(task_id))
    finally:
        loop.close()


async def dispatch_notifications(should_stop_callable: Callable[[], bool], poll_interval: float = 1.0):
    """Continuously polls for notifications and dispatches them to subscribers.

    Args:
        should_stop_callable: A callable that returns True when the dispatcher should stop
        poll_interval: Time in seconds to wait between polling for notifications
    """
    task_orchestration_service = get_task_orchestration_service()
    while not should_stop_callable():
        notifications = task_orchestration_service.get_notifications()
        for notification in notifications:
            if notification.input_request:
                # Get flow data from the database using flow_id

                async with task_orchestration_service.db.with_session() as session:
                    # Only select the data column we need
                    result = await session.exec(select(Flow.data).where(Flow.id == notification.flow_id))
                    flow_data = result.first()

                if flow_data:
                    # If we have both flow data and input request, dispatch to simple_run_flow_task_celery
                    logger.info(
                        f"Dispatching notification for task {notification.task_id} to flow {notification.flow_id}"
                    )
                    simple_run_flow_task_celery.delay(
                        flow_data=flow_data,
                        input_request=notification.input_request,
                        stream=False,  # You might want to make this configurable
                    )
                else:
                    logger.warning(f"Flow {notification.flow_id} not found or has no data")
            else:
                logger.debug(f"Skipping notification for task {notification.task_id} - missing input request")
        await asyncio.sleep(poll_interval)


class NotificationDispatcher:
    """Dispatches notifications to subscribed flows using Celery tasks."""

    def __init__(self, poll_interval: float = 1.0):
        self.should_stop = False
        self.task = None
        self.poll_interval = poll_interval
        self.task_orchestration_service = get_task_orchestration_service()

    async def start(self):
        """Start the notification dispatcher."""
        self.task = asyncio.create_task(self.run())

    async def stop(self):
        """Stop the notification dispatcher."""
        self.should_stop = True
        if self.task:
            await self.task

    async def run(self):
        """Run the notification dispatcher."""
        await dispatch_notifications(lambda: self.should_stop, self.poll_interval)


notification_dispatcher = NotificationDispatcher()
