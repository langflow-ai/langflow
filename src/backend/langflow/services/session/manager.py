from typing import TYPE_CHECKING
from langflow.interface.run import build_sorted_vertices
from langflow.services.base import Service
from langflow.services.cache.utils import compute_dict_hash

from langflow.services.session.utils import session_id_generator

if TYPE_CHECKING:
    from langflow.services.cache.base import BaseCacheManager


class SessionManager(Service):
    name = "session_manager"

    def __init__(self, cache_manager):
        self.cache_manager: "BaseCacheManager" = cache_manager

    def load_session(self, key, data_graph):
        # Check if the data is cached
        if key in self.cache_manager:
            return self.cache_manager.get(key)

        # If not cached, build the graph and cache it
        graph, artifacts = build_sorted_vertices(data_graph)
        self.cache_manager.set(key, (graph, artifacts))

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

    def update_session(self, session_id, data_graph, value):
        key = self.build_key(session_id, data_graph)
        self.cache_manager.set(key, value)

    def clear_session(self, session_id, data_graph):
        key = self.build_key(session_id, data_graph)
        self.cache_manager.delete(key)
