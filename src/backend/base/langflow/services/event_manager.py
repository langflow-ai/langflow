"""
Event Manager for Webhook Real-Time Updates.

This module provides an in-memory event broadcasting system for webhook builds.
When a UI is connected via SSE, it receives real-time build events.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any

from loguru import logger


class WebhookEventManager:
    """
    Manages SSE connections and broadcasts build events for webhooks.

    When a flow is open in the UI, it subscribes to webhook events.
    When a webhook is triggered, events are emitted to all subscribers.

    This provides the same visual experience as clicking "Play" in the UI,
    but triggered by external webhook calls.
    """

    def __init__(self):
        """Initialize the event manager with empty listeners."""
        # flow_id → set of queues (one per SSE connection)
        self._listeners: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()
        logger.debug("WebhookEventManager initialized")

    async def subscribe(self, flow_id: str) -> asyncio.Queue:
        """
        Subscribe to receive events for a specific flow.

        Args:
            flow_id: The flow ID to subscribe to

        Returns:
            Queue that will receive events for this flow
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._listeners[flow_id].add(queue)
            listener_count = len(self._listeners[flow_id])

        logger.info(f"New subscriber for flow {flow_id}. Total listeners: {listener_count}")
        return queue

    async def unsubscribe(self, flow_id: str, queue: asyncio.Queue) -> None:
        """
        Unsubscribe from flow events.

        Args:
            flow_id: The flow ID to unsubscribe from
            queue: The queue to remove
        """
        async with self._lock:
            if flow_id in self._listeners:
                self._listeners[flow_id].discard(queue)
                listener_count = len(self._listeners[flow_id])

                # Clean up empty sets
                if not self._listeners[flow_id]:
                    del self._listeners[flow_id]
                    logger.info(f"All subscribers disconnected for flow {flow_id}")
                else:
                    logger.info(f"Subscriber disconnected from flow {flow_id}. Remaining: {listener_count}")

    async def emit(self, flow_id: str, event_type: str, data: Any) -> None:
        """
        Emit an event to all subscribers of a flow.

        Args:
            flow_id: The flow ID to emit to
            event_type: Type of event (build_start, end_vertex, etc.)
            data: Event data (will be JSON serialized)
        """
        async with self._lock:
            listeners = self._listeners.get(flow_id, set()).copy()

        if not listeners:
            # No one listening, skip emission (performance optimization)
            return

        logger.debug(f"Emitting {event_type} to {len(listeners)} listeners for flow {flow_id}")

        # Prepare event
        event = {
            "event": event_type,
            "data": data,
            "timestamp": time.time(),
        }

        # Send to all queues
        dead_queues: set[asyncio.Queue] = set()

        for queue in listeners:
            try:
                # Try to put with timeout to avoid blocking
                await asyncio.wait_for(queue.put(event), timeout=1.0)
            except asyncio.TimeoutError:
                # Queue is full (slow consumer), skip this event
                logger.warning(f"Queue full for flow {flow_id}, dropping event {event_type}")
            except Exception as e:
                # Queue is closed or broken, mark for removal
                logger.error(f"Error putting event in queue for flow {flow_id}: {e}")
                dead_queues.add(queue)

        # Clean up dead queues
        if dead_queues:
            async with self._lock:
                if flow_id in self._listeners:
                    self._listeners[flow_id] -= dead_queues
                    if not self._listeners[flow_id]:
                        del self._listeners[flow_id]

    def has_listeners(self, flow_id: str) -> bool:
        """
        Check if there are any active listeners for a flow.

        This is used to determine if we should emit events or not.
        If no one is listening, we skip event emission for performance.

        Args:
            flow_id: The flow ID to check

        Returns:
            True if there are active listeners, False otherwise
        """
        return flow_id in self._listeners and len(self._listeners[flow_id]) > 0

    def get_listener_count(self, flow_id: str) -> int:
        """
        Get the number of active listeners for a flow.

        Args:
            flow_id: The flow ID to check

        Returns:
            Number of active listeners
        """
        return len(self._listeners.get(flow_id, set()))

    async def emit_multiple(self, flow_id: str, events: list[tuple[str, Any]]) -> None:
        """
        Emit multiple events at once (batch emission).

        Args:
            flow_id: The flow ID to emit to
            events: List of (event_type, data) tuples
        """
        for event_type, data in events:
            await self.emit(flow_id, event_type, data)


# Global singleton instance
webhook_event_manager = WebhookEventManager()
