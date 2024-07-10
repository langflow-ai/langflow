from typing import Coroutine, Optional

from langflow.services.base import Service
from langflow.services.cache.base import CacheService
from langflow.services.session.utils import compute_dict_hash, session_id_generator


class SessionService(Service):
    name = "session_service"

    def __init__(self, cache_service):
        self.cache_service: "CacheService" = cache_service

    async def load_session(self, key, flow_id: str, data_graph: Optional[dict] = None):
        # Check if the data is cached
        if key in self.cache_service:
            result = self.cache_service.get(key)
            if isinstance(result, Coroutine):
                result = await result
            return result

        if key is None:
            key = self.generate_key(session_id=None, data_graph=data_graph)
        if data_graph is None:
            return (None, None)
        # If not cached, build the graph and cache it
        from langflow.graph.graph.base import Graph

        graph = Graph.from_payload(data_graph, flow_id=flow_id)
        artifacts: dict = {}
        await self.cache_service.set(key, (graph, artifacts))

        return graph, artifacts

    def build_key(self, session_id, data_graph):
        json_hash = compute_dict_hash(data_graph)
        return f"{session_id}{':' if session_id else ''}{json_hash}"

    def generate_key(self, session_id, data_graph):
        # Hash the JSON and combine it with the session_id to create a unique key
        if session_id is None:
            # generate a 5 char session_id to concatenate with the json_hash
            session_id = session_id_generator()
        return self.build_key(session_id, data_graph=data_graph)

    async def update_session(self, session_id, value):
        result = self.cache_service.set(session_id, value)
        # if it is a coroutine, await it
        if isinstance(result, Coroutine):
            await result

    async def clear_session(self, session_id):
        result = self.cache_service.delete(session_id)
        # if it is a coroutine, await it
        if isinstance(result, Coroutine):
            await result
