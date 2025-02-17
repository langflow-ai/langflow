"""Simplified consumer implementation for task processing."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from loguru import logger

from langflow.services.database.models.task.model import TaskUpdate
from langflow.services.deps import get_event_bus_service, get_task_orchestration_service


class ConsumerWorker:
    """Consumes events from the EventBus and coordinates task processing."""

    def __init__(self):
        """Initialize the consumer worker."""
        self.task_orchestration_service = get_task_orchestration_service()
        self.event_bus_service = get_event_bus_service()
        self.notification_service = NotificationService()
        self._tasks: list[asyncio.Task[Any]] = []

    async def start(self):
        """Start the consumer worker, subscribing to events."""
        try:
            # Subscribe to task lifecycle events
            await self.event_bus_service.subscribe("TaskCreated", self.handle_task_created)
            await self.event_bus_service.subscribe("TaskCompleted", self.handle_task_completed_or_failed)
            await self.event_bus_service.subscribe("TaskFailed", self.handle_task_completed_or_failed)

            # Start notification service
            notification_task = asyncio.create_task(self.notification_service.start())
            self._tasks.append(notification_task)

            logger.info("ConsumerWorker started")
        except Exception as e:
            logger.error(f"Error starting ConsumerWorker: {e}")
            raise

    async def stop(self):
        """Stop the consumer worker and clean up tasks."""
        try:
            for task in self._tasks:
                if not task.done():
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
            self._tasks.clear()
            logger.info("ConsumerWorker stopped")
        except Exception as e:
            logger.error(f"Error stopping ConsumerWorker: {e}")
            raise

    async def handle_task_created(self, payload: dict[str, Any]):
        """Handle TaskCreated event by updating task status and starting processing.

        Args:
            payload: Event payload containing task information
        """
        task_id = payload["task_id"]
        logger.info(f"ConsumerWorker: Received TaskCreated event for task_id: {task_id}")

        try:
            # Update task status to processing
            await self.task_orchestration_service.update_task(
                task_id, TaskUpdate(status="processing", state=payload.get("state"))
            )

            # Publish TaskProcessingStarted event
            await self.event_bus_service.publish(
                "TaskProcessingStarted",
                {
                    "task_id": task_id,
                    "flow_id": payload["flow_id"],
                    "input_request": payload["input_request"],
                },
            )
        except ValueError as e:
            logger.error(f"Error handling TaskCreated event for task {task_id}: {e}")
            # Ensure task is marked as failed if we can't process it
            try:
                await self.task_orchestration_service.update_task(
                    task_id,
                    TaskUpdate(
                        status="failed",
                        state="error",
                        result={"error": f"Failed to process task: {e!s}"},
                    ),
                )
            except ValueError as update_error:
                logger.error(f"Error updating failed task {task_id}: {update_error}")

    async def handle_task_completed_or_failed(self, payload: dict[str, Any]):
        """Handle TaskCompleted/TaskFailed events by updating task status.

        Args:
            payload: Event payload containing task result
        """
        task_id = payload["task_id"]
        status = "completed" if payload.get("event_type") == "TaskCompleted" else "failed"
        logger.info(f"ConsumerWorker: Received {status} event for task_id: {task_id}")

        try:
            # Update task status and result
            await self.task_orchestration_service.update_task(
                task_id,
                TaskUpdate(
                    status=status,
                    state=payload.get("state"),
                    result=payload.get("result"),
                ),
            )
        except ValueError as e:
            logger.error(f"Error handling {status} event for task {task_id}: {e}")


class NotificationService:
    """Handles sending notifications to subscribers based on task events."""

    def __init__(self):
        """Initialize the notification service."""
        self.event_bus_service = get_event_bus_service()
        self.subscribers: dict[str, Callable[[dict[str, Any]], Any]] = {}  # flow_id: callback

    async def start(self):
        """Start the notification service, subscribing to task events."""
        try:
            await self.event_bus_service.subscribe("TaskCreated", self.handle_notification)
            await self.event_bus_service.subscribe("TaskUpdated", self.handle_notification)
            await self.event_bus_service.subscribe("TaskCompleted", self.handle_notification)
            await self.event_bus_service.subscribe("TaskFailed", self.handle_notification)
            logger.info("NotificationService started")
        except Exception as e:
            logger.error(f"Error starting NotificationService: {e}")
            raise

    async def handle_notification(self, payload: dict[str, Any]):
        """Handle task events and send notifications to subscribers.

        Args:
            payload: Event payload containing task information
        """
        flow_id = payload.get("flow_id")
        event_type = payload.get("event_type")
        task_id = payload.get("task_id")
        status = payload.get("status")
        result = payload.get("result")

        logger.info(
            f"NotificationService: Received {event_type} for task_id: {task_id}, flow_id: {flow_id}, status: {status}"
        )

        # If there's a subscriber for this flow, notify them
        if flow_id in self.subscribers:
            try:
                await self.subscribers[flow_id](payload)
            except ValueError as e:
                logger.error(f"Error notifying subscriber for flow {flow_id}: {e}")

        # Log the notification for debugging
        logger.info(f"Notification: Flow {flow_id}, Task {task_id} - {event_type}, Status: {status}, Result: {result}")

    async def subscribe(self, flow_id: str, callback: Callable[[dict[str, Any]], Any]):
        """Subscribe a callback to receive notifications for a flow.

        Args:
            flow_id: Flow identifier
            callback: Async callback function to be called with notifications
        """
        self.subscribers[flow_id] = callback
        logger.info(f"Subscribed to notifications for flow_id: {flow_id}")

    async def unsubscribe(self, flow_id: str):
        """Unsubscribe from notifications for a flow.

        Args:
            flow_id: Flow identifier to unsubscribe from
        """
        if flow_id in self.subscribers:
            del self.subscribers[flow_id]
            logger.info(f"Unsubscribed from notifications for flow_id: {flow_id}")
