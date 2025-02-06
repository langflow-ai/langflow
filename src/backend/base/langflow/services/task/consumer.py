import asyncio
from collections.abc import Callable

from celery import shared_task
from loguru import logger
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.task.model import TaskUpdate
from langflow.services.deps import get_db_service, get_event_bus_service, get_task_orchestration_service
from langflow.worker import simple_run_flow_task_celery


@shared_task
def consume_task_celery(task_id: str):
    """Celery task (fallback/direct invocation)."""
    service = get_task_orchestration_service()
    from langflow.core.celery_app import celery_app  # Adjust import

    if celery_app.conf.task_always_eager:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_consume_task, service, task_id)
            return future.result()
    else:
        from asgiref.sync import async_to_sync

        return async_to_sync(service.consume_task)(task_id)  # Still calls the old method


def _run_consume_task(service, task_id):
    """Helper function."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(service.consume_task(task_id))
    finally:
        loop.close()


# No longer used
async def dispatch_notifications(should_stop_callable: Callable[[], bool], poll_interval: float = 1.0):
    pass


# No longer used
class NotificationDispatcher:
    pass


# Event-Driven Consumer
class ConsumerWorker:
    """Consumes events from the EventBus and performs actions."""

    def __init__(self):
        self.task_orchestration_service = get_task_orchestration_service()
        self.event_bus_service = get_event_bus_service()
        self.flow_worker = FlowWorker()  # Instantiate FlowWorker

    async def start(self):
        """Start the consumer worker, subscribing to events."""
        await self.event_bus_service.subscribe("TaskCreated", self.handle_task_created)
        await self.event_bus_service.subscribe("TaskCompleted", self.handle_task_completed_or_failed)
        await self.event_bus_service.subscribe("TaskFailed", self.handle_task_completed_or_failed)
        await self.flow_worker.start()  # Start FlowWorker
        await self.start_notification_service()  # Start NotificationService

    async def handle_task_created(self, payload: dict):
        """Handle TaskCreated event."""
        task_id = payload["task_id"]
        logger.info(f"ConsumerWorker: Received TaskCreated event for task_id: {task_id}")

        # Update task status
        await self.task_orchestration_service.update_task(
            task_id, TaskUpdate(status="processing", state=payload.get("state"))
        )

        # Publish TaskProcessingStarted
        await self.event_bus_service.publish(
            "TaskProcessingStarted",
            {
                "task_id": task_id,
                "flow_id": payload["flow_id"],
                "input_request": payload["input_request"],
            },
        )

    async def handle_task_completed_or_failed(self, payload: dict):
        """Handle TaskCompleted/TaskFailed events."""
        task_id = payload["task_id"]
        status = "completed" if payload.get("event_type") == "TaskCompleted" else "failed"
        logger.info(f"ConsumerWorker: Received {status} event for task_id: {task_id}")

        # Update task status and result
        await self.task_orchestration_service.update_task(
            task_id, TaskUpdate(status=status, state=payload.get("state"), result=payload.get("result"))
        )

    async def start_notification_service(self):
        """Starts the NotificationService."""
        self.notification_service = NotificationService()
        if not hasattr(self, "_tasks"):
            self._tasks = []
        task = asyncio.create_task(self.notification_service.start())
        self._tasks.append(task)


# FlowWorker (Simplified - Enqueues Celery Task)
class FlowWorker:
    """Subscribes to TaskProcessingStarted and enqueues the run_flow_task_event Celery task."""

    def __init__(self):
        self.event_bus_service = get_event_bus_service()

    async def start(self):
        """Start, subscribing to TaskProcessingStarted."""
        await self.event_bus_service.subscribe("TaskProcessingStarted", self.handle_task_processing_started)

    async def handle_task_processing_started(self, payload: dict):
        """Handle TaskProcessingStarted, enqueue Celery task."""
        task_id = payload["task_id"]
        flow_id = payload["flow_id"]
        input_request = payload["input_request"]
        logger.info(f"FlowWorker: Received TaskProcessingStarted, enqueuing run_flow_task_event for task_id: {task_id}")

        # Enqueue the Celery task
        run_flow_task_event.delay(task_id=task_id, flow_id=flow_id, input_request=input_request)


# New Celery Task for Flow Execution
@shared_task
def run_flow_task_event(task_id: str, flow_id: str, input_request: dict):
    """Celery task to execute the flow logic.  This is the core processing unit."""
    logger.info(f"run_flow_task_event: Starting for task_id: {task_id}, flow_id: {flow_id}")
    db_service = get_db_service()  # Get db_service *inside* the task
    event_bus_service = get_event_bus_service()  # Get event_bus_service *inside* the task

    try:
        # Get flow data (synchronous within the Celery task is fine)
        with db_service.sync_session() as session:  # Use sync_session
            result = session.exec(select(Flow.data).where(Flow.id == flow_id))
            flow_data = result.first()

        if not flow_data:
            msg = f"Flow data not found for flow_id: {flow_id}"
            raise ValueError(msg)

        # Execute flow logic
        result = simple_run_flow_task_celery.delay(flow_data=flow_data, input_request=input_request, stream=False)
        result_data = result.get()  # Get the result (this blocks)

        # Publish TaskCompleted event
        asyncio.run(
            event_bus_service.publish(  # Use asyncio.run
                "TaskCompleted",
                {
                    "event_type": "TaskCompleted",
                    "task_id": task_id,
                    "flow_id": flow_id,
                    "result": result_data,
                    "state": "success",
                },
            )
        )

    except Exception as e:  # noqa: BLE001
        logger.error(f"run_flow_task_event: Error processing task {task_id}: {e}")
        # Publish TaskFailed event
        asyncio.run(
            event_bus_service.publish(  # Use asyncio.run
                "TaskFailed",
                {
                    "event_type": "TaskFailed",
                    "task_id": task_id,
                    "flow_id": flow_id,
                    "result": {"error": str(e)},
                    "state": "error",
                },
            )
        )


class NotificationService:
    """Handles sending notifications to subscribers based on task events."""

    def __init__(self):
        self.event_bus_service = get_event_bus_service()
        # In a real implementation, you'd have a mechanism to manage subscribers
        # (e.g., a database table, a separate service, etc.).  For this example,
        # we'll just log the notifications.
        self.subscribers = {}  # flow_id: callback

    async def start(self):
        """Start the notification service, subscribing to relevant events."""
        await self.event_bus_service.subscribe("TaskCreated", self.handle_notification)
        await self.event_bus_service.subscribe("TaskUpdated", self.handle_notification)
        # You might want separate events for Completed/Failed if you need
        # different notification logic for those.

    async def handle_notification(self, payload: dict):
        """Handle task events and send notifications."""
        flow_id = payload.get("flow_id")
        event_type = payload.get("event_type")  # TaskCreated, TaskUpdated
        task_id = payload.get("task_id")
        status = payload.get("status")  # e.g., "completed", "failed"
        result = payload.get("result")

        logger.info(
            f"NotificationService: Received {event_type} for task_id: {task_id}, flow_id: {flow_id}, status: {status}"
        )

        # In a real implementation, you would look up subscribers for the flow_id
        # and send them the notification.  This could involve sending emails,
        # pushing to web sockets, etc.
        # Example:
        # if flow_id in self.subscribers:
        #     await self.subscribers[flow_id](payload)  # Call the subscriber's callback

        # For this example, we'll just log:
        logger.info(
            f"  Notification: Flow {flow_id}, Task {task_id} - {event_type}, Status: {status}, Result: {result}"
        )

    async def subscribe(self, flow_id: str, callback: Callable):
        """Subscribe a callback to receive notifications for a flow."""
        self.subscribers[flow_id] = callback
        logger.info(f"Subscribed to notifications for flow_id: {flow_id}")

    async def unsubscribe(self, flow_id: str):
        """Unsubscribe from notifications for a flow."""
        if flow_id in self.subscribers:
            del self.subscribers[flow_id]
            logger.info(f"Unsubscribed from notifications for flow_id: {flow_id}")
