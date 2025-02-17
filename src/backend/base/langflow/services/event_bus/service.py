import asyncio
from collections import defaultdict
from collections.abc import Callable

from loguru import logger

from langflow.services.base import Service


class EventBusService(Service):
    """A simplified in-memory event bus for internal communication.

    This implementation uses asyncio for asynchronous event handling.
    It's suitable for single-process deployments and prototyping.
    """

    name = "event_bus_service"

    def __init__(self):
        """Initialize the event bus service."""
        self._subscribers: defaultdict[str, list[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task] = []

    async def connect(self):
        """No-op for in-memory implementation."""
        logger.info("Event bus ready (in-memory mode)")

    async def disconnect(self):
        """Clean up any running tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()
        logger.info("Event bus stopped")

    async def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe a callback to an event type.

        Args:
            event_type: The type of event to subscribe to
            callback: The async callback function to be called when the event occurs
        """
        async with self._lock:
            self._subscribers[event_type].append(callback)
            logger.info(f"Added subscriber for event type: {event_type}")

    async def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe a callback from an event type.

        Args:
            event_type: The type of event to unsubscribe from
            callback: The callback function to remove
        """
        async with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.info(f"Removed subscriber for event type: {event_type}")

    async def publish(self, event_type: str, payload: dict) -> None:
        """Publish an event to all subscribers.

        Args:
            event_type: The type of event being published
            payload: The event data to be sent to subscribers
        """
        logger.info(f"Publishing event: {event_type} with payload: {payload}")

        # Get all subscribers for this event type
        subscribers = self._subscribers.get(event_type, [])

        # Create tasks for each subscriber
        for callback in subscribers:
            try:
                # Create a new task for each callback to run concurrently
                task = asyncio.create_task(callback(payload))
                self._tasks.append(task)

                # Clean up completed tasks
                try:
                    self._tasks = [t for t in self._tasks if not t.done()]
                except ValueError as e:
                    logger.error(f"Error scheduling callback for event {event_type}: {e}")
            except (asyncio.InvalidStateError, TypeError) as e:
                logger.error(f"Error scheduling callback for event {event_type}: {e}")
