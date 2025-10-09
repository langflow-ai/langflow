"""Abstract base class for queue services."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from loguru import logger

from langflow.services.base import Service

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from langflow.services.database.service import DatabaseService

T = TypeVar("T")


class AbstractQueueService(Service, ABC, Generic[T]):
    """Abstract base class for queue services with batching capabilities."""

    name = "abstract_queue_service"

    def __init__(
        self,
        database_service: DatabaseService,
        max_queue_size: int = 10000,
        batch_size: int = 100,
        flush_interval: float = 3.0,
    ):
        """Initialize the abstract queue service.

        Args:
            database_service: The database service for persistence.
            max_queue_size: Maximum number of items to queue.
            batch_size: Number of items to process in a batch.
            flush_interval: Interval in seconds to flush the queue.
        """
        super().__init__()
        self._database_service = database_service
        self._max_queue_size = max_queue_size
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._queue: asyncio.Queue[T | None] = asyncio.Queue(maxsize=max_queue_size)
        self._worker_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._items_processed = 0
        self._items_dropped = 0

    @abstractmethod
    async def process_batch(self, items: list[T]) -> None:
        """Process a batch of items.

        This method must be implemented by subclasses to handle
        the specific processing logic for each queue type.

        Args:
            items: List of items to process.
        """

    @abstractmethod
    def get_item_info(self, item: T) -> dict[str, Any]:
        """Get information about an item for logging.

        Args:
            item: The item to get info about.

        Returns:
            Dictionary with item information.
        """

    async def start(self) -> None:
        """Start the queue service and background worker."""
        if self._worker_task is None or self._worker_task.done():
            self._stop_event.clear()
            self._worker_task = asyncio.create_task(self._worker())
            logger.info(f"Started {self.__class__.__name__} worker")

    async def stop(self) -> None:
        """Stop the queue service and flush remaining items."""
        logger.info(f"Stopping {self.__class__.__name__}...")
        self._stop_event.set()

        # Add sentinel to wake up worker
        with suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)

        # Wait for worker to finish
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(f"{self.__class__.__name__} worker didn't stop gracefully")
                self._worker_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._worker_task

        # Log final stats
        logger.info(
            f"{self.__class__.__name__} stopped. Processed: {self._items_processed}, Dropped: {self._items_dropped}"
        )

    async def _worker(self) -> None:
        """Background worker to process queued items in batches."""
        batch: list[T] = []
        last_flush = asyncio.get_event_loop().time()

        while not self._stop_event.is_set():
            try:
                # Wait for an item with timeout
                timeout = max(0.1, self._flush_interval - (asyncio.get_event_loop().time() - last_flush))
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    item = None

                # Check if we got a sentinel (None means stop)
                if item is None and self._stop_event.is_set():
                    break

                # Add item to batch if not None
                if item is not None:
                    batch.append(item)

                # Check if we should flush the batch
                current_time = asyncio.get_event_loop().time()
                should_flush = (
                    len(batch) >= self._batch_size
                    or (batch and current_time - last_flush >= self._flush_interval)
                    or self._stop_event.is_set()
                )

                if should_flush and batch:
                    await self._flush_batch(batch)
                    batch = []
                    last_flush = current_time

            except Exception:  # noqa: BLE001
                logger.exception(f"Error in {self.__class__.__name__} worker")
                # Continue processing to avoid stopping the worker
                continue

        # Final flush
        if batch:
            await self._flush_batch(batch)

    async def _flush_batch(self, batch: list[T]) -> None:
        """Flush a batch of items.

        Args:
            batch: List of items to flush.
        """
        if not batch:
            return

        try:
            await self.process_batch(batch)
            self._items_processed += len(batch)
            logger.debug(f"Flushed {len(batch)} items from {self.__class__.__name__}")
        except Exception:  # noqa: BLE001
            logger.exception(f"Failed to flush batch in {self.__class__.__name__}")
            # Log some info about the failed items
            for item in batch[:3]:  # Log first 3 items
                try:
                    info = self.get_item_info(item)
                    logger.debug(f"Failed item info: {info}")
                except Exception:  # noqa: BLE001, S110
                    pass

    async def enqueue(self, item: T) -> bool:
        """Add an item to the queue.

        Args:
            item: The item to enqueue.

        Returns:
            True if the item was enqueued, False if dropped.
        """
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self._items_dropped += 1
            if self._items_dropped % 100 == 1:  # Log every 100 drops
                logger.warning(f"{self.__class__.__name__} queue full. Total dropped: {self._items_dropped}")
            return False
        else:
            return True

    @asynccontextmanager
    async def session_context(self) -> AsyncGenerator:
        """Get a database session context."""
        async with self._database_service.session_scope() as session:
            yield session

    @property
    def queue_size(self) -> int:
        """Get the current queue size."""
        return self._queue.qsize()

    @property
    def stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "queue_size": self.queue_size,
            "items_processed": self._items_processed,
            "items_dropped": self._items_dropped,
            "max_queue_size": self._max_queue_size,
            "batch_size": self._batch_size,
            "flush_interval": self._flush_interval,
        }
