"""Transaction queue service for batch processing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.graph.vertex.base import Vertex
from loguru import logger

from langflow.graph.utils import batch_insert_transactions_to_db
from langflow.services.queue.abstract import AbstractQueueService

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService

# Transaction tuple: (flow_id, source, status, target, error)
TransactionData = tuple[str | UUID, Vertex, str, Vertex | None, str | None]


class TransactionQueueService(AbstractQueueService[TransactionData]):
    """Service for queuing and batch processing transaction data."""

    name = "transaction_queue_service"

    def __init__(
        self,
        database_service: DatabaseService,
        max_queue_size: int = 10000,
        batch_size: int = 100,
        flush_interval: float = 3.0,
    ):
        """Initialize the transaction queue service.

        Args:
            database_service: The database service for persistence.
            max_queue_size: Maximum number of items to queue.
            batch_size: Number of items to process in a batch.
            flush_interval: Interval in seconds to flush the queue.
        """
        super().__init__(database_service, max_queue_size, batch_size, flush_interval)

    async def process_batch(self, items: list[TransactionData]) -> None:
        """Process a batch of transaction data.

        Args:
            items: List of transaction tuples to process.
        """
        if not items:
            return

        try:
            # Use the existing batch_insert_transactions_to_db function
            async with self.session_context() as session:
                await batch_insert_transactions_to_db(items, session)
                logger.debug(f"Successfully processed {len(items)} transactions")
        except Exception:
            logger.exception(f"Failed to process batch of {len(items)} transactions")
            raise

    def get_item_info(self, item: TransactionData) -> dict[str, Any]:
        """Get information about a transaction for logging.

        Args:
            item: The transaction tuple to get info about.

        Returns:
            Dictionary with transaction information.
        """
        flow_id, source, status, target, error = item
        return {
            "flow_id": str(flow_id),
            "source_id": source.id if source else None,
            "status": status,
            "target_id": target.id if target else None,
            "error": error[:100] if error else None,  # Truncate error message
        }

    async def add_transaction(
        self,
        flow_id: str | UUID,
        source: Vertex,
        status: str,
        target: Vertex | None = None,
        error: str | None = None,
    ) -> bool:
        """Add a transaction to the queue.

        Args:
            flow_id: The flow ID.
            source: The source vertex.
            status: The transaction status.
            target: The target vertex (optional).
            error: The error message (optional).

        Returns:
            True if the transaction was queued, False if dropped.
        """
        transaction = (flow_id, source, status, target, error)
        return await self.enqueue(transaction)
