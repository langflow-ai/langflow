from __future__ import annotations

import sys
from copy import deepcopy
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

    async def add_flow_to_cache(self, flow: Flow, *, silent: bool = False) -> None:
        """Add a flow's Graph instance to the cache.

        Args:
            flow (Flow): The flow to cache
            silent (bool): If True, suppress debug logging (used during refresh)
        """
        if flow.data is None:
            if not silent:
                logger.warning(f"Flow {flow.id} has no data, skipping cache")
            return

        from lfx.graph.graph.base import Graph

        flow_id_str = str(flow.id)
        graph_data = flow.data.copy()

        # Parse the Graph payload, catch parsing issues
        try:
            graph = Graph.from_payload(graph_data, flow_id=flow_id_str, user_id=flow.user_id, flow_name=flow.name)
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            if not silent:
                logger.warning(f"Flow {flow_id_str} cannot be cached due to parsing error: {e!s}")
            return

        # Store in cache, catch cache-specific errors
        try:
            await self.set(flow_id_str, graph)
            if flow.endpoint_name:
                await self.set(flow.endpoint_name, graph)
            if not silent:
                logger.debug(f"Added flow {flow_id_str} to cache")
        except (KeyError, RuntimeError) as e:
            logger.error(f"Error caching graph for flow {flow_id_str}: {e!s}")

    async def remove_flow_from_cache(
        self, flow: Flow, *, silent: bool = False, old_endpoint_name: str | None = None
    ) -> None:
        """Remove a flow's Graph instance from the cache.

        Removes all cache keys associated with the flow: UUID, current endpoint_name,
        and optionally a previous endpoint_name (for handling renames).

        Args:
            flow (Flow): The flow to remove from cache
            silent (bool): If True, suppress debug logging (used during refresh)
            old_endpoint_name (str | None): Previous endpoint name to remove (for renames)
        """
        flow_id_str = str(flow.id)

        # Collect all keys to remove: UUID + current endpoint + old endpoint
        keys_to_remove = [flow_id_str]
        if flow.endpoint_name:
            keys_to_remove.append(flow.endpoint_name)
        if old_endpoint_name:
            keys_to_remove.append(old_endpoint_name)

        # Remove each key independently
        for key in keys_to_remove:
            try:
                await self.delete(key)
                if not silent:
                    logger.debug(f"Removed cache key: {key}")
            except KeyError:
                if not silent:
                    logger.debug(f"Cache key not found: {key}")
            except RuntimeError as e:
                logger.error(f"Error removing cache key {key}: {e!s}")

    async def get_cached_graph(self, flow_id: str) -> Graph | None:
        """Get a cached Graph instance for a flow.

        Returns a deep copy to prevent concurrent requests from mutating shared state.

        Args:
            flow_id (str): The flow ID to look up

        Returns:
            Graph | None: A deep copy of the cached Graph instance or None if not found
        """
        try:
            cached = await self.get(flow_id)
            # Check for cache miss sentinel
            if not cached:
                return None
            # Return a deep copy to prevent concurrent requests from sharing mutable state
            return deepcopy(cached)

        except KeyError as e:
            logger.error(f"Cache miss retrieving graph for flow {flow_id}: {e!s}")
        except RuntimeError as e:
            logger.error(f"Error retrieving cached graph for flow {flow_id}: {e!s}")
        return None

    async def refresh_flow_in_cache(self, flow: Flow, *, old_endpoint_name: str | None = None) -> None:
        """Refresh a flow's Graph instance in the cache.

        This removes the existing cached version (if any) and adds the updated version.
        Useful when a deployed flow's data has been modified or endpoint renamed.

        Args:
            flow (Flow): The flow to refresh in cache
            old_endpoint_name (str | None): Previous endpoint name to remove (for renames)
        """
        flow_id_str = str(flow.id)
        try:
            # Remove old version from cache, including old endpoint alias if provided
            await self.remove_flow_from_cache(flow, silent=True, old_endpoint_name=old_endpoint_name)
            # Add updated version to cache with new endpoint name
            await self.add_flow_to_cache(flow, silent=True)
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
