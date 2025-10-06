from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from loguru import logger

from langflow.services.cache.service import AsyncInMemoryCache

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph

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

        from lfx.graph.graph.base import Graph

        flow_id_str = str(flow.id)
        graph_data = flow.data.copy()

        # Parse the Graph payload, catch parsing issues
        try:
            graph = Graph.from_payload(graph_data, flow_id=flow_id_str, user_id=flow.user_id, flow_name=flow.name)
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing graph payload for flow {flow_id_str}: {e!s}")
            return

        # Store in cache, catch cache-specific errors
        try:
            await self.set(flow_id_str, graph)
            if flow.endpoint_name:
                await self.set(flow.endpoint_name, graph)
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

    async def refresh_flow_in_cache(self, flow: Flow) -> None:
        """Refresh a flow's Graph instance in the cache.

        This removes the existing cached version (if any) and adds the updated version.
        Useful when a deployed flow's data has been modified.

        Args:
            flow (Flow): The flow to refresh in cache
        """
        flow_id_str = str(flow.id)
        try:
            # Remove old version from cache
            await self.remove_flow_from_cache(flow)
            # Add updated version to cache
            await self.add_flow_to_cache(flow)
            logger.debug(f"Refreshed flow {flow_id_str} in cache")
        except (KeyError, RuntimeError) as e:
            logger.error(f"Error refreshing flow {flow_id_str} in cache: {e!s}")

    async def get_cache_stats(self) -> dict[str, int | float | list[str] | None]:
        """Get statistics about the current cache state.

        Returns:
            dict: Dictionary containing:
                - size: Number of items in cache
                - max_size: Maximum cache size (None if unlimited)
                - keys: List of cached flow identifiers (IDs and endpoint names)
                - memory_bytes: Approximate memory usage in bytes
                - memory_mb: Approximate memory usage in megabytes
        """
        try:
            async with self.lock:
                cache_size = len(self.cache)
                cache_keys = list(self.cache.keys())

                # Calculate approximate memory footprint
                # Note: This is an approximation using sys.getsizeof
                # The cache structure is: {key: {"value": Graph, "time": float}}
                total_bytes = sys.getsizeof(self.cache)
                for key, cache_entry in self.cache.items():
                    # Add size of the key (flow ID or endpoint name string)
                    total_bytes += sys.getsizeof(key)
                    # Add size of the cache entry dict wrapper
                    total_bytes += sys.getsizeof(cache_entry)

                    # Add size of the actual cached content
                    if isinstance(cache_entry, dict):
                        # Get the actual Graph object (or pickled bytes)
                        cached_value = cache_entry.get("value")
                        if cached_value is not None:
                            total_bytes += sys.getsizeof(cached_value)
                        # Add timestamp
                        cached_time = cache_entry.get("time")
                        if cached_time is not None:
                            total_bytes += sys.getsizeof(cached_time)

                memory_mb = total_bytes / (1024 * 1024)

        except (KeyError, RuntimeError) as e:
            logger.error(f"Error getting cache stats: {e!s}")
            return {
                "size": 0,
                "max_size": self.max_size,
                "keys": [],
                "memory_bytes": 0,
                "memory_mb": 0.0,
            }
        else:
            return {
                "size": cache_size,
                "max_size": self.max_size,
                "keys": cache_keys,
                "memory_bytes": total_bytes,
                "memory_mb": round(memory_mb, 2),
            }
