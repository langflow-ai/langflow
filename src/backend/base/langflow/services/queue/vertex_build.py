"""Vertex build queue service for batch processing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from loguru import logger

from langflow.graph.utils import batch_insert_vertex_builds_to_db
from langflow.services.queue.abstract import AbstractQueueService

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService

# Vertex build tuple: (flow_id, vertex_id, valid, params, result_dict, artifacts)
VertexBuildData = tuple[str | UUID, str, bool, dict, dict, dict | None]


class VertexBuildQueueService(AbstractQueueService[VertexBuildData]):
    """Service for queuing and batch processing vertex build data."""

    name = "vertex_build_queue_service"

    def __init__(
        self,
        database_service: DatabaseService,
        max_queue_size: int = 10000,
        batch_size: int = 100,
        flush_interval: float = 3.0,
    ):
        """Initialize the vertex build queue service.

        Args:
            database_service: The database service for persistence.
            max_queue_size: Maximum number of items to queue.
            batch_size: Number of items to process in a batch.
            flush_interval: Interval in seconds to flush the queue.
        """
        super().__init__(database_service, max_queue_size, batch_size, flush_interval)

    async def process_batch(self, items: list[VertexBuildData]) -> None:
        """Process a batch of vertex build data.

        Args:
            items: List of vertex build tuples to process.
        """
        if not items:
            return

        try:
            # Use the existing batch_insert_vertex_builds_to_db function
            async with self.session_context() as session:
                await batch_insert_vertex_builds_to_db(items, session)
                logger.debug(f"Successfully processed {len(items)} vertex builds")
        except Exception:
            logger.exception(f"Failed to process batch of {len(items)} vertex builds")
            raise

    def get_item_info(self, item: VertexBuildData) -> dict[str, Any]:
        """Get information about a vertex build for logging.

        Args:
            item: The vertex build tuple to get info about.

        Returns:
            Dictionary with vertex build information.
        """
        flow_id, vertex_id, valid, params, _result_dict, _artifacts = item
        return {
            "flow_id": str(flow_id),
            "vertex_id": vertex_id,
            "valid": valid,
            "params_count": len(params),
        }

    async def add_vertex_build(
        self,
        flow_id: str | UUID,
        vertex_id: str,
        valid: bool,  # noqa: FBT001
        params: dict,
        result_dict: dict,
        artifacts: dict | None = None,
    ) -> bool:
        """Add a vertex build to the queue.

        Args:
            flow_id: The flow ID.
            vertex_id: The vertex ID.
            valid: Whether the build was valid.
            params: The parameters used.
            result_dict: The result dictionary.
            artifacts: Optional artifacts dictionary.

        Returns:
            True if the vertex build was queued, False if dropped.
        """
        vertex_build = (flow_id, vertex_id, valid, params, result_dict, artifacts)
        return await self.enqueue(vertex_build)
