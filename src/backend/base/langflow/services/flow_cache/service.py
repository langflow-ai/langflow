from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from langflow.services.cache.service import AsyncInMemoryCache

if TYPE_CHECKING:
    from langflow.graph.graph.base import Graph
    from langflow.services.database.models.flow import Flow


class FlowCacheService(AsyncInMemoryCache):
    """A cache service for storing and retrieving Flow Graph instances.

    This service provides an in-memory cache for Graph instances created from Flow data.
    It's designed to improve performance by avoiding repeated Graph creation for deployed flows.
    """

    name = "flow_cache_service"

    async def add_flow_to_cache(self, flow: Flow) -> None:
        """Add a flow's Graph instance to the cache.

        Args:
            flow (Flow): The flow to cache
        """
        if flow.data is None:
            logger.warning(f"Flow {flow.id} has no data, skipping cache")
            return

        from langflow.graph.graph.base import Graph

        flow_id_str = str(flow.id)
        graph_data = flow.data.copy()

        # Parse the Graph payload, catch parsing issues
        try:
            graph = Graph.from_payload(graph_data, flow_id=flow_id_str)
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing graph payload for flow {flow_id_str}: {e!s}")
            return

        # Store in cache, catch cache-specific errors
        try:
            await self.set(flow_id_str, graph)
            logger.debug(f"Added flow {flow_id_str} to cache")
        except (KeyError, RuntimeError) as e:
            logger.error(f"Error caching graph for flow {flow_id_str}: {e!s}")

    async def remove_flow_from_cache(self, flow: Flow) -> None:
        """Remove a flow's Graph instance from the cache.

        Args:
            flow (Flow): The flow to remove from cache
        """
        flow_id_str = str(flow.id)
        try:
            await self.delete(flow_id_str)
            logger.debug(f"Removed flow {flow_id_str} from cache")
        except KeyError as e:
            logger.error(f"Cache key not found when removing flow {flow_id_str}: {e!s}")
        except RuntimeError as e:
            logger.error(f"Error removing flow {flow_id_str} from cache: {e!s}")

    async def get_cached_graph(self, flow_id: str) -> Graph | None:
        """Get a cached Graph instance for a flow.

        Args:
            flow_id (str): The flow ID to look up

        Returns:
            Graph | None: The cached Graph instance or None if not found
        """
        try:
            return await self.get(flow_id)
        except KeyError as e:
            logger.error(f"Cache miss retrieving graph for flow {flow_id}: {e!s}")
        except RuntimeError as e:
            logger.error(f"Error retrieving cached graph for flow {flow_id}: {e!s}")
        return None
