import asyncio
from typing import TYPE_CHECKING

from langflow.services.base import Service
from langflow.services.cache.base import AsyncBaseCacheService
from langflow.services.cache.utils import CacheMiss
from langflow.services.session.utils import compute_dict_hash, session_id_generator

if TYPE_CHECKING:
    from langflow.services.cache.base import CacheService


class SessionService(Service):
    name = "session_service"

    def __init__(self, cache_service) -> None:
        self.cache_service: CacheService | AsyncBaseCacheService = cache_service

    async def load_session(self, key, flow_id: str, data_graph: dict | None = None):
        # Check if the data is cached
        if isinstance(self.cache_service, AsyncBaseCacheService):
            value = await self.cache_service.get(key)
        else:
            value = await asyncio.to_thread(self.cache_service.get, key)
        if not isinstance(value, CacheMiss):
            return value

        if key is None:
            key = self.generate_key(session_id=None, data_graph=data_graph)
        if data_graph is None:
            return None, None
        # If not cached, build the graph and cache it
        from langflow.graph.graph.base import Graph

        graph = Graph.from_payload(data_graph, flow_id=flow_id)
        artifacts: dict = {}
        await self.cache_service.set(key, (graph, artifacts))

        return graph, artifacts

    def build_key(self, session_id, data_graph) -> str:
        json_hash = compute_dict_hash(data_graph)
        return f"{session_id}{':' if session_id else ''}{json_hash}"

    def generate_key(self, session_id, data_graph):
        # Hash the JSON and combine it with the session_id to create a unique key
        if session_id is None:
            # generate a 5 char session_id to concatenate with the json_hash
            session_id = session_id_generator()
        return self.build_key(session_id, data_graph=data_graph)

    async def update_session(self, session_id, value) -> None:
        if isinstance(self.cache_service, AsyncBaseCacheService):
            await self.cache_service.set(session_id, value)
        else:
            await asyncio.to_thread(self.cache_service.set, session_id, value)

    async def clear_session(self, session_id) -> None:
        if isinstance(self.cache_service, AsyncBaseCacheService):
            await self.cache_service.delete(session_id)
        else:
            await asyncio.to_thread(self.cache_service.delete, session_id)
