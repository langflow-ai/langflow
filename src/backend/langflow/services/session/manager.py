from langflow.interface.run import build_sorted_vertices
from langflow.services.base import Service
from langflow.services.cache.utils import compute_dict_hash


class SessionManager(Service):
    name = "session_manager"

    def __init__(self, cache_manager):
        self.cache_manager = cache_manager

    def load_session(self, session_id, data_graph):
        key = self.generate_key(session_id, data_graph)

        # Check if the data is cached
        if key in self.cache_manager:
            return self.cache_manager.get(key)

        # If not cached, build the graph and cache it
        graph, artifacts = build_sorted_vertices(data_graph)
        self.cache_manager.set(key, (graph, artifacts))

        return graph, artifacts

    def generate_key(self, session_id, data_graph):
        # Hash the JSON and combine it with the session_id to create a unique key
        json_hash = compute_dict_hash(data_graph)
        return f"{session_id}{':' if session_id else ''}{json_hash}"

    def update_session(self, session_id, data_graph, value):
        key = self.generate_key(session_id, data_graph)
        self.cache_manager.set(key, value)

    def clear_session(self, session_id, data_graph):
        key = self.generate_key(session_id, data_graph)
        self.cache_manager.delete(key)

    # Additional methods to handle session-related logic
