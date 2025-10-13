"""Priority queue for batched message writes with backpressure."""

import asyncio
import contextlib
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from langflow.services.database.models.message.model import MessageTable


class MessageWriteQueue:
    """Priority queue for message writes with size limits and batching.

    Provides batched writes to reduce database contention while maintaining
    message ordering and priority.
    """

    def __init__(self, max_queue_size: int = 1000, batch_size: int = 100, flush_interval: float = 2.0):
        """Initialize message write queue.

        Args:
            max_queue_size: Maximum queue size before backpressure (default: 1000)
            batch_size: Number of messages to batch per write (default: 100)
            flush_interval: Seconds between flushes (default: 2.0)
        """
        self._queue: asyncio.Queue = asyncio.Queue()
        self._batch_size = batch_size
        self._max_queue_size = max_queue_size
        self._flush_interval = flush_interval
        self._flush_task: asyncio.Task | None = None
        self._running = False
        self._total_queued = 0
        self._total_flushed = 0

    async def start(self) -> None:
        """Start background worker that flushes batches."""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.create_task(self._background_flush_worker())
        logger.debug("Message write queue worker started")

    async def stop(self) -> None:
        """Stop background worker and flush remaining messages."""
        if not self._running:
            return

        self._running = False

        # Cancel the background task
        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task

        # Flush any remaining messages
        await self._flush_remaining()

        logger.debug(
            f"Message write queue stopped. Total queued: {self._total_queued}, Total flushed: {self._total_flushed}"
        )

    async def queue_message(self, message: "MessageTable") -> None:
        """Queue message for batch write.

        If queue is full, performs immediate blocking write (backpressure).

        Args:
            message: Message to write
        """
        if self._queue.qsize() >= self._max_queue_size:
            # Backpressure - queue is full, write immediately
            logger.warning(f"Message queue full ({self._max_queue_size}), applying backpressure with immediate write")
            await self._flush_immediate([message])
            return

        await self._queue.put(message)
        self._total_queued += 1

    async def _background_flush_worker(self) -> None:
        """Background worker that flushes batches periodically."""
        while self._running:
            batch = []

            try:
                # Wait for first message or timeout
                first_message = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=self._flush_interval,
                )
                batch.append(first_message)

                # Collect more messages up to batch_size (non-blocking)
                while len(batch) < self._batch_size:
                    try:
                        message = self._queue.get_nowait()
                        batch.append(message)
                    except asyncio.QueueEmpty:
                        break

                # Flush the batch
                await self._flush_batch(batch)

            except asyncio.TimeoutError:
                # No messages received within flush_interval, continue waiting
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                logger.error(f"Error in message flush worker: {e}")
                await asyncio.sleep(1)  # Back off on error

    async def _flush_batch(self, messages: list["MessageTable"]) -> None:
        """Flush a batch of messages to database.

        Args:
            messages: Messages to flush
        """
        if not messages:
            return

        try:
            async with session_scope() as session:
                for message in messages:
                    session.add(message)
                await session.commit()

                # Refresh to get database-generated values
                for message in messages:
                    await session.refresh(message)

                self._total_flushed += len(messages)
                logger.debug(f"Flushed {len(messages)} messages to database")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error flushing message batch: {exc}")
            # TODO: Add retry logic or dead letter queue

    async def _flush_immediate(self, messages: list["MessageTable"]) -> None:
        """Immediately flush messages (used for backpressure).

        Args:
            messages: Messages to flush immediately
        """
        try:
            async with session_scope() as session:
                for message in messages:
                    session.add(message)
                await session.commit()

                for message in messages:
                    await session.refresh(message)

                logger.debug(f"Immediately flushed {len(messages)} messages (backpressure)")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error in immediate message flush: {exc}")

    async def _flush_remaining(self) -> None:
        """Flush all remaining messages in queue during shutdown."""
        remaining = []

        # Drain the queue
        while not self._queue.empty():
            try:
                message = self._queue.get_nowait()
                remaining.append(message)
            except asyncio.QueueEmpty:
                break

        if remaining:
            logger.info(f"Flushing {len(remaining)} remaining messages during shutdown")
            await self._flush_batch(remaining)

    def get_stats(self) -> dict:
        """Get queue statistics.

        Returns:
            Dictionary with queue stats
        """
        return {
            "queue_size": self._queue.qsize(),
            "max_queue_size": self._max_queue_size,
            "batch_size": self._batch_size,
            "total_queued": self._total_queued,
            "total_flushed": self._total_flushed,
            "pending": self._total_queued - self._total_flushed,
        }
