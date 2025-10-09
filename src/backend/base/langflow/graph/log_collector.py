"""Log collector implementation for batched database writes.

This module provides collectors that implement the callback interfaces
to accumulate transactions and vertex builds for batch processing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.graph.callbacks import LogCallbacks
    from lfx.graph.vertex.base import Vertex

    from langflow.services.database.service import DatabaseService
    from langflow.services.queue.transaction import TransactionQueueService
    from langflow.services.queue.vertex_build import VertexBuildQueueService


# Type alias for vertex build data
VertexBuildData = tuple["str | UUID", str, bool, dict[str, Any], dict[str, Any], dict[str, Any] | None]


class TransactionCollector:
    """Collects transactions for batch processing."""

    def __init__(self) -> None:
        """Initialize the transaction collector."""
        self.transactions: list[tuple[str | UUID, Vertex, str, Vertex | None, Any]] = []

    def collect_transaction(
        self,
        flow_id: str | UUID,
        source: Vertex,
        status: str,
        target: Vertex | None = None,
        error: Any = None,
    ) -> None:
        """Collect a transaction for later batch processing.

        Args:
            flow_id: The flow identifier
            source: Source vertex
            status: Transaction status
            target: Optional target vertex
            error: Optional error information
        """
        self.transactions.append((flow_id, source, status, target, error))

    def get_and_clear(self) -> list[tuple[str | UUID, Vertex, str, Vertex | None, Any]]:
        """Get all collected transactions and clear the collection.

        Returns:
            List of transaction tuples ready for batch processing
        """
        transactions = self.transactions
        self.transactions = []
        return transactions


class VertexBuildCollector:
    """Collects vertex builds for batch processing."""

    def __init__(self) -> None:
        """Initialize the vertex build collector."""
        self.builds: list[VertexBuildData] = []

    def collect_vertex_build(
        self,
        flow_id: str | UUID,
        vertex_id: str,
        *,
        valid: bool,
        params: dict[str, Any],
        result_dict: dict[str, Any],
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        """Collect a vertex build for later batch processing.

        Args:
            flow_id: The flow identifier
            vertex_id: ID of the vertex that was built
            valid: Whether the build was valid
            params: Build parameters
            result_dict: Build results
            artifacts: Optional build artifacts
        """
        self.builds.append((flow_id, vertex_id, valid, params, result_dict, artifacts))

    def get_and_clear(self) -> list[VertexBuildData]:
        """Get all collected builds and clear the collection.

        Returns:
            List of vertex build tuples ready for batch processing
        """
        builds = self.builds.copy()
        self.builds.clear()
        return builds


def create_log_callbacks() -> tuple[LogCallbacks, TransactionCollector, VertexBuildCollector]:
    """Create log callbacks with collectors for batch processing.

    Returns:
        Tuple of (callbacks, transaction_collector, vertex_build_collector)
    """
    from lfx.graph.callbacks import LogCallbacks

    transaction_collector = TransactionCollector()
    vertex_build_collector = VertexBuildCollector()

    callbacks = LogCallbacks(
        transaction_callback=transaction_collector.collect_transaction,
        vertex_build_callback=vertex_build_collector.collect_vertex_build,
    )

    return callbacks, transaction_collector, vertex_build_collector


def create_log_callbacks_with_queue_services(
    database_service: DatabaseService,
    *,
    max_queue_size: int = 10000,
    batch_size: int = 100,
    flush_interval: float = 3.0,
) -> tuple[LogCallbacks, TransactionQueueService, VertexBuildQueueService]:
    """Create log callbacks using queue services for async batch processing.

    This provides automatic batching and background processing of transactions
    and vertex builds, with better performance and reliability than manual
    collectors.

    Args:
        database_service: Database service for persistence
        max_queue_size: Maximum items to queue before dropping
        batch_size: Number of items to process in each batch
        flush_interval: Time in seconds between automatic flushes

    Returns:
        Tuple of (callbacks, transaction_service, vertex_build_service)
    """
    from lfx.graph.callbacks import LogCallbacks

    from langflow.services.queue.transaction import TransactionQueueService
    from langflow.services.queue.vertex_build import VertexBuildQueueService

    # Create queue services
    transaction_service = TransactionQueueService(
        database_service=database_service,
        max_queue_size=max_queue_size,
        batch_size=batch_size,
        flush_interval=flush_interval,
    )

    vertex_build_service = VertexBuildQueueService(
        database_service=database_service,
        max_queue_size=max_queue_size,
        batch_size=batch_size,
        flush_interval=flush_interval,
    )

    # Create callbacks that use the queue services
    callbacks = LogCallbacks(
        transaction_callback=transaction_service.add_transaction,
        vertex_build_callback=vertex_build_service.add_vertex_build,
    )

    return callbacks, transaction_service, vertex_build_service
