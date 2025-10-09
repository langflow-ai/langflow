"""In-memory cache for recent messages with TTL."""

import asyncio
import contextlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from langflow.services.database.models.message.model import MessageTable


class MessageCache:
    """In-memory cache for recent messages with TTL.

    Provides fast access to recently added messages for UI responsiveness
    while background workers persist them to the database.
    """

    def __init__(self, ttl_seconds: int = 300):
        """Initialize message cache.

        Args:
            ttl_seconds: Time-to-live for cached messages (default: 5 minutes)
        """
        self._cache: dict[str, list[MessageTable]] = defaultdict(list)
        self._cache_times: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self.ttl_seconds = ttl_seconds
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the cache cleanup background task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_worker())
            logger.debug("Message cache cleanup worker started")

    async def stop(self) -> None:
        """Stop the cache cleanup background task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
            logger.debug("Message cache cleanup worker stopped")

    async def add_message(self, session_id: str, message: "MessageTable") -> None:
        """Add message to cache immediately (non-blocking).

        Args:
            session_id: Session ID for the message
            message: Message to cache
        """
        async with self._lock:
            self._cache[session_id].append(message)
            self._cache_times[session_id] = datetime.now(timezone.utc)

    async def add_messages(self, session_id: str, messages: list["MessageTable"]) -> None:
        """Add multiple messages to cache.

        Args:
            session_id: Session ID for the messages
            messages: Messages to cache
        """
        async with self._lock:
            self._cache[session_id].extend(messages)
            self._cache_times[session_id] = datetime.now(timezone.utc)

    async def get_messages(self, session_id: str) -> list["MessageTable"] | None:
        """Get messages from cache if available.

        Args:
            session_id: Session ID to retrieve messages for

        Returns:
            List of cached messages, or None if not in cache or expired
        """
        async with self._lock:
            if session_id not in self._cache:
                return None

            # Check if cache entry is expired
            cache_time = self._cache_times.get(session_id)
            if cache_time:
                age = datetime.now(timezone.utc) - cache_time
                if age > timedelta(seconds=self.ttl_seconds):
                    # Expired - remove from cache
                    del self._cache[session_id]
                    del self._cache_times[session_id]
                    return None

            # Return a copy to prevent external modification
            return self._cache[session_id].copy()

    async def clear_session(self, session_id: str) -> None:
        """Clear messages for a specific session.

        Args:
            session_id: Session ID to clear
        """
        async with self._lock:
            self._cache.pop(session_id, None)
            self._cache_times.pop(session_id, None)

    async def clear_all(self) -> None:
        """Clear all cached messages."""
        async with self._lock:
            self._cache.clear()
            self._cache_times.clear()

    async def _cleanup_worker(self) -> None:
        """Background worker that removes expired cache entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute

                async with self._lock:
                    now = datetime.now(timezone.utc)
                    expired_sessions = [
                        session_id
                        for session_id, cache_time in self._cache_times.items()
                        if now - cache_time > timedelta(seconds=self.ttl_seconds)
                    ]

                    for session_id in expired_sessions:
                        del self._cache[session_id]
                        del self._cache_times[session_id]

                    if expired_sessions:
                        logger.debug(f"Cleaned up {len(expired_sessions)} expired cache entries")

            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                logger.error(f"Error in cache cleanup worker: {e}")
                await asyncio.sleep(5)  # Back off on error

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "cached_sessions": len(self._cache),
            "total_messages": sum(len(msgs) for msgs in self._cache.values()),
            "ttl_seconds": self.ttl_seconds,
        }
