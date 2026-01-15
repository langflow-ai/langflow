"""Event Manager for Webhook Real-Time Updates.

This module provides an in-memory event broadcasting system for webhook builds.
When a UI is connected via SSE, it receives real-time build events.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any

from loguru import logger

# Constants
SSE_QUEUE_MAX_SIZE = 100
SSE_EMIT_TIMEOUT_SECONDS = 1.0
SECONDS_PER_MINUTE = 60


class WebhookEventManager:
    """Manages SSE connections and broadcasts build events for webhooks.

    When a flow is open in the UI, it subscribes to webhook events.
    When a webhook is triggered, events are emitted to all subscribers.

    This provides the same visual experience as clicking "Play" in the UI,
    but triggered by external webhook calls.
    """

    def __init__(self):
        """Initialize the event manager with empty listeners."""
        self._listeners: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._vertex_start_times: dict[str, dict[str, float]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    def record_build_start(self, flow_id: str, vertex_id: str) -> None:
        """Record when a vertex build starts for duration calculation."""
        self._vertex_start_times[flow_id][vertex_id] = time.time()

    def get_build_duration(self, flow_id: str, vertex_id: str) -> str | None:
        """Get the formatted build duration for a vertex."""
        start_time = self._vertex_start_times.get(flow_id, {}).get(vertex_id)
        if start_time is None:
            return None
        elapsed = time.time() - start_time
        # Clean up
        self._vertex_start_times[flow_id].pop(vertex_id, None)
        return self._format_duration(elapsed)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in a human-readable way."""
        if seconds < 1:
            return f"{int(seconds * 1000)} ms"
        if seconds < SECONDS_PER_MINUTE:
            return f"{seconds:.1f} s"
        minutes = int(seconds // SECONDS_PER_MINUTE)
        secs = seconds % SECONDS_PER_MINUTE
        return f"{minutes}m {secs:.1f}s"

    async def subscribe(self, flow_id: str) -> asyncio.Queue:
        """Subscribe to receive events for a specific flow.

        Args:
            flow_id: The flow ID to subscribe to

        Returns:
            Queue that will receive events for this flow
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=SSE_QUEUE_MAX_SIZE)
        async with self._lock:
            self._listeners[flow_id].add(queue)
            listener_count = len(self._listeners[flow_id])

        logger.info(f"New subscriber for flow {flow_id}. Total listeners: {listener_count}")
        return queue

    async def unsubscribe(self, flow_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from flow events.

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
        """Emit an event to all subscribers of a flow.

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
                await asyncio.wait_for(queue.put(event), timeout=SSE_EMIT_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                # Queue is full (slow consumer), skip this event
                logger.warning(f"Queue full for flow {flow_id}, dropping event {event_type}")
            except Exception as e:  # noqa: BLE001
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
        """Check if there are any active listeners for a flow."""
        return flow_id in self._listeners and len(self._listeners[flow_id]) > 0


# Module-level instance (can be replaced in tests via dependency injection)
# TODO: Consider migrating to langflow's service manager pattern for better DI
_webhook_event_manager: WebhookEventManager | None = None


def get_webhook_event_manager() -> WebhookEventManager:
    """Get the webhook event manager instance.

    Returns:
        The WebhookEventManager singleton instance.
    """
    global _webhook_event_manager  # noqa: PLW0603
    if _webhook_event_manager is None:
        _webhook_event_manager = WebhookEventManager()
    return _webhook_event_manager


# Backwards compatibility alias
webhook_event_manager = get_webhook_event_manager()
