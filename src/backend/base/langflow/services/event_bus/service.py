import asyncio
import json
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING

import redis.asyncio as redis
from loguru import logger

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class EventBusService(Service):
    """An event bus for internal communication using Redis Streams.

    This implementation uses redis.asyncio for asynchronous interaction with Redis.
    It's suitable for multi-process deployments and provides persistence and
    scalability.
    """

    name = "event_bus_service"

    def __init__(self, settings_service: "SettingsService"):
        self._subscribers: defaultdict[str, list[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self.redis_client = None
        self.stream_name = "langflow_events"  # Define a stream name
        self.settings_service = settings_service
        self.redis_url = self.settings_service.settings.redis_url  # Get Redis URL from settings
        self.consumer_group_name = "langflow_consumers"  # Consumer group name
        self._stream_id = "$"  # Default to reading from latest message

    def set_stream_id(self, stream_id: str) -> None:
        """Set the stream ID to read from.

        Args:
            stream_id (str): The stream ID to read from. Use "$" to read from latest
                message, or "0-0" to read from beginning of stream.
        """
        self._stream_id = stream_id

    async def connect(self):
        """Establish connection to Redis."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url)
        try:
            # Create the consumer group (it's idempotent, so it's safe to call repeatedly)
            await self.redis_client.xgroup_create(
                name=self.stream_name, groupname=self.consumer_group_name, id=self._stream_id, mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):  # Ignore if group already exists
                raise
            logger.info(f"Consumer group '{self.consumer_group_name}' already exists.")
        logger.info("Connected to Redis")

    async def disconnect(self):
        """Close connection to Redis."""
        if self.redis_client:
            await self.redis_client.aclose()
            logger.info("Disconnected from Redis")

    async def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe a callback to an event type."""
        if self.redis_client is None:
            msg = "Redis client not initialized"
            raise RuntimeError(msg)
        async with self._lock:
            self._subscribers[event_type].append(callback)
            logger.info(f"Added subscriber for event type: {event_type}")

        # Create a unique consumer group for this subscriber
        consumer_group = f"{self.consumer_group_name}-{id(callback)}"
        try:
            if self.redis_client:
                await self.redis_client.xgroup_create(
                    name=self.stream_name,
                    groupname=consumer_group,
                    id=self._stream_id,
                    mkstream=True,
                )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        # Start a background task to consume messages for this event type.
        # We use a separate task per subscriber to avoid blocking.
        if not hasattr(self, "_tasks"):
            self._tasks = []
        task = asyncio.create_task(self.consume_messages(event_type, callback, consumer_group))
        self._tasks.append(task)

    async def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe a callback from an event type."""
        async with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.info(f"Removed subscriber for event type: {event_type}")

    async def publish(self, event_type: str, payload: dict) -> None:
        """Publish an event to the Redis stream."""
        logger.info(f"Publishing event: {event_type} with payload: {payload}")
        if self.redis_client is None:
            msg = "Redis client not initialized"
            raise RuntimeError(msg)
        # Convert payload to JSON string and add event_type
        payload_with_type = {"event_type": event_type, **payload}
        message = json.dumps(payload_with_type, default=str).encode()

        # Publish the message to the stream
        await self.redis_client.xadd(name=self.stream_name, fields={"data": message})

    async def consume_messages(self, event_type: str, callback: Callable, consumer_group: str):
        """Consume messages from the stream for a specific event type."""
        if self.redis_client is None:
            msg = "Redis client not initialized"
            raise RuntimeError(msg)
        # Use a unique consumer name within the consumer group for each subscriber.
        consumer_name = f"consumer-{event_type}-{id(callback)}"
        # Use the configured stream ID
        last_id = self._stream_id

        while True:
            try:
                # Read messages from the stream using XREADGROUP
                response = await self.redis_client.xreadgroup(
                    groupname=consumer_group,
                    consumername=consumer_name,
                    streams={self.stream_name: last_id},
                    count=1,  # Read one message at a time
                    block=0,  # Non-blocking read (0 means return immediately)
                )

                if response:
                    for _stream, messages in response:
                        for message_id, message_data in messages:
                            try:
                                # Decode the message data
                                decoded_data = json.loads(message_data[b"data"].decode())
                                received_event_type = decoded_data.get("event_type")

                                # Skip initialization messages
                                if received_event_type == "init":
                                    await self.redis_client.xack(
                                        self.stream_name,
                                        consumer_group,
                                        message_id,
                                    )
                                    continue

                                # Check if the received event type matches the subscribed event type
                                if received_event_type == event_type:
                                    # Remove event_type from the payload before passing to the callback
                                    payload = decoded_data.copy()
                                    del payload["event_type"]
                                    await callback(payload)  # Call the callback with a copy of the data

                                # Always acknowledge the message
                                await self.redis_client.xack(
                                    self.stream_name,
                                    consumer_group,
                                    message_id,
                                )
                                last_id = message_id  # Update the last ID for the next read
                            except Exception as e:  # noqa: BLE001
                                logger.error(f"Error processing message: {e}")
                                # Still acknowledge the message even if there was an error
                                await self.redis_client.xack(
                                    self.stream_name,
                                    consumer_group,
                                    message_id,
                                )
            except redis.ConnectionError as e:
                logger.error(f"Redis connection error: {e}")
                await asyncio.sleep(5)  # Wait before reconnecting
            except Exception as e:  # noqa: BLE001
                logger.exception(f"Unexpected error in consumer: {e}")
                await asyncio.sleep(1)  # Short delay to prevent busy-looping
            await asyncio.sleep(0.1)  # Small delay to avoid busy-waiting
