import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Awaitable, Callable, List

if TYPE_CHECKING:
    from langflow.graph.graph.base import Graph
    from langflow.graph.vertex.base import Vertex


class RunnableVerticesManager:
    def __init__(self):
        self.run_map = defaultdict(list)  # Tracks successors of each vertex
        self.run_predecessors = defaultdict(set)  # Tracks predecessors for each vertex
        self.vertices_to_run = set()  # Set of vertices that are ready to run

    def is_vertex_runnable(self, vertex_id: str) -> bool:
        """Determines if a vertex is runnable."""

        return vertex_id in self.vertices_to_run and not self.run_predecessors.get(vertex_id)

    def find_runnable_predecessors_for_successors(self, vertex_id: str) -> List[str]:
        """Finds runnable predecessors for the successors of a given vertex."""
        runnable_vertices = []
        visited = set()

        for successor_id in self.run_map.get(vertex_id, []):
            for predecessor_id in self.run_predecessors.get(successor_id, []):
                if predecessor_id not in visited and self.is_vertex_runnable(predecessor_id):
                    runnable_vertices.append(predecessor_id)
                    visited.add(predecessor_id)
        return runnable_vertices

    def remove_from_predecessors(self, vertex_id: str):
        """Removes a vertex from the predecessor list of its successors."""
        predecessors = self.run_map.get(vertex_id, [])
        for predecessor in predecessors:
            if vertex_id in self.run_predecessors[predecessor]:
                self.run_predecessors[predecessor].remove(vertex_id)

    def build_run_map(self, graph):
        """Builds a map of vertices and their runnable successors."""
        self.run_map = defaultdict(list)
        for vertex_id, predecessors in graph.predecessor_map.items():
            for predecessor in predecessors:
                self.run_map[predecessor].append(vertex_id)
        self.run_predecessors = graph.predecessor_map.copy()
        self.vertices_to_run = graph.vertices_to_run

    def update_vertex_run_state(self, vertex_id: str, is_runnable: bool):
        """Updates the runnable state of a vertex."""
        if is_runnable:
            self.vertices_to_run.add(vertex_id)
        else:
            self.vertices_to_run.discard(vertex_id)

    async def get_next_runnable_vertices(
        self,
        lock: asyncio.Lock,
        set_cache_coro: Callable[["Graph", asyncio.Lock], Awaitable[None]],
        graph: "Graph",
        vertex: "Vertex",
    ):
        """
        Retrieves the next runnable vertices in the graph for a given vertex.

        Args:
            graph (Graph): The graph object representing the flow.
            vertex (Vertex): The current vertex.
            vertex_id (str): The ID of the current vertex.
            chat_service (ChatService): The chat service object.
            flow_id (str): The ID of the flow.

        Returns:
            list: A list of IDs of the next runnable vertices.

        """
        async with lock:
            self.remove_from_predecessors(vertex.id)
            direct_successors_ready = [v for v in vertex.successors_ids if self.is_vertex_runnable(v)]
            if not direct_successors_ready:
                # No direct successors ready, look for runnable predecessors of successors
                next_runnable_vertices = self.find_runnable_predecessors_for_successors(vertex.id)
            else:
                next_runnable_vertices = direct_successors_ready

            for v_id in set(next_runnable_vertices):  # Use set to avoid duplicates
                self.update_vertex_run_state(v_id, is_runnable=False)
                self.remove_from_predecessors(v_id)
            await set_cache_coro(data=graph, lock=lock)  # type: ignore
        return next_runnable_vertices

    @staticmethod
    def get_top_level_vertices(graph, vertices_ids):
        """
        Retrieves the top-level vertices from the given graph based on the provided vertex IDs.

        Args:
            graph (Graph): The graph object containing the vertices.
            vertices_ids (list): A list of vertex IDs.

        Returns:
            list: A list of top-level vertex IDs.

        """
        top_level_vertices = []
        for vertex_id in vertices_ids:
            vertex = graph.get_vertex(vertex_id)
            if vertex.parent_is_top_level:
                top_level_vertices.append(vertex.parent_node_id)
            else:
                top_level_vertices.append(vertex_id)
        return top_level_vertices
