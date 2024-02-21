from collections import defaultdict, deque
from typing import Dict, Generator, List, Optional, Type, Union

from langchain.chains.base import Chain
from langflow.graph.edge.base import ContractEdge
from langflow.graph.graph.constants import lazy_load_vertex_dict
from langflow.graph.graph.utils import process_flow
from langflow.graph.schema import InterfaceComponentTypes
from langflow.graph.vertex.base import Vertex
from langflow.graph.vertex.types import (
    ChatVertex,
    FileToolVertex,
    LLMVertex,
    ToolkitVertex,
)
from langflow.interface.tools.constants import FILE_TOOLS
from langflow.utils import payload
from loguru import logger


class Graph:
    """A class representing a graph of vertices and edges."""

    def __init__(
        self,
        nodes: List[Dict],
        edges: List[Dict[str, str]],
    ) -> None:
        self.inputs = []
        self.outputs = []
        self._vertices = nodes
        self._edges = edges
        self.raw_graph_data = {"nodes": nodes, "edges": edges}
        self._runs = 0
        self._updates = 0

        self.top_level_vertices = []
        for vertex in self._vertices:
            if vertex_id := vertex.get("id"):
                self.top_level_vertices.append(vertex_id)
        self._graph_data = process_flow(self.raw_graph_data)

        self._vertices = self._graph_data["nodes"]
        self._edges = self._graph_data["edges"]

        self._build_graph()
        self.build_graph_maps()

    @property
    def metadata(self):
        return {
            "runs": self._runs,
            "updates": self._updates,
        }

    def build_graph_maps(self):
        self.predecessor_map, self.successor_map = self.build_adjacency_maps()
        self.in_degree_map = self.build_in_degree()

    def increment_run_count(self):
        self._runs += 1

    def increment_update_count(self):
        self._updates += 1

    def __getstate__(self):
        return self.raw_graph_data

    def __setstate__(self, state):
        self.__init__(**state)

    def build_in_degree(self):
        in_degree = defaultdict(int)
        for edge in self.edges:
            in_degree[edge.target_id] += 1
        return in_degree

    def build_adjacency_maps(self):
        """Returns the adjacency maps for the graph."""
        predecessor_map = defaultdict(list)
        successor_map = defaultdict(list)
        for edge in self.edges:
            predecessor_map[edge.target_id].append(edge.source_id)
            successor_map[edge.source_id].append(edge.target_id)
        return predecessor_map, successor_map

    @classmethod
    def from_payload(cls, payload: Dict) -> "Graph":
        """
        Creates a graph from a payload.

        Args:
            payload (Dict): The payload to create the graph from.˜`

        Returns:
            Graph: The created graph.
        """
        if "data" in payload:
            payload = payload["data"]
        try:
            vertices = payload["nodes"]
            edges = payload["edges"]
            return cls(vertices, edges)
        except KeyError as exc:
            logger.exception(exc)
            raise ValueError(
                f"Invalid payload. Expected keys 'nodes' and 'edges'. Found {list(payload.keys())}"
            ) from exc

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Graph):
            return False
        return self.__repr__() == other.__repr__()

    # update this graph with another graph by comparing the __repr__ of each vertex
    # and if the __repr__ of a vertex is not the same as the other
    # then update the .data of the vertex to the self
    # both graphs have the same vertices and edges
    # but the data of the vertices might be different

    def update(self, other: "Graph") -> None:
        # Existing vertices in self graph
        existing_vertex_ids = set(vertex.id for vertex in self.vertices)
        # Vertex IDs in the other graph
        other_vertex_ids = set(other.vertex_map.keys())

        # Find vertices that are in other but not in self (new vertices)
        new_vertex_ids = other_vertex_ids - existing_vertex_ids

        # Find vertices that are in self but not in other (removed vertices)
        removed_vertex_ids = existing_vertex_ids - other_vertex_ids

        # Update existing vertices that have changed
        for vertex_id in existing_vertex_ids.intersection(other_vertex_ids):
            self_vertex = self.get_vertex(vertex_id)
            other_vertex = other.get_vertex(vertex_id)
            if self_vertex.__repr__() != other_vertex.__repr__():
                self_vertex.data = other_vertex.data
                self_vertex.params = {}
                self_vertex._build_params()
                self_vertex.graph = self
                self_vertex._built = False
                self.reset_all_edges_of_vertex(self_vertex)

        # Remove vertices
        for vertex_id in removed_vertex_ids:
            self.remove_vertex(vertex_id)

        # Add new vertices
        for vertex_id in new_vertex_ids:
            new_vertex = other.get_vertex(vertex_id)
            self._add_vertex(new_vertex)

        self.build_graph_maps()
        self.increment_update_count()
        return self

    def reset_all_edges_of_vertex(self, vertex: Vertex) -> None:
        """Resets all the edges of a vertex."""
        for edge in vertex.edges:
            for vid in [edge.source_id, edge.target_id]:
                if vid in self.vertex_map:
                    _vertex = self.vertex_map[vid]
                    if not _vertex.pinned:
                        _vertex._build_params()

    def _add_vertex(self, vertex: Vertex) -> None:
        """Adds a new vertex to the graph."""
        self.vertices.append(vertex)
        self.vertex_map[vertex.id] = vertex
        # Vertex has edges, so we need to update the edges
        for edge in vertex.edges:
            if edge.source_id in self.vertex_map and edge.target_id in self.vertex_map:
                self.edges.append(edge)

    def _build_graph(self) -> None:
        """Builds the graph from the vertices and edges."""
        self.vertices = self._build_vertices()
        self.vertex_map = {vertex.id: vertex for vertex in self.vertices}
        self.edges = self._build_edges()

        # This is a hack to make sure that the LLM vertex is sent to
        # the toolkit vertex
        self._build_vertex_params()
        # remove invalid vertices
        self._validate_vertices()
        # Now that we have the vertices and edges
        # We need to map the vertices that are connected to
        # to ChatVertex instances
        self._map_chat_vertices()

    def _map_chat_vertices(self) -> None:
        """Maps the vertices that are connected to ChatVertex instances."""
        # For each edge, we need to check if the source or target vertex is a ChatVertex
        # If it is, we need to update the other vertex `is_external` attribute
        # and store the id of the ChatVertex in the attributes self.inputs and self.outputs
        for edge in self.edges:
            source_vertex = self.get_vertex(edge.source_id)
            target_vertex = self.get_vertex(edge.target_id)
            if isinstance(source_vertex, ChatVertex):
                # The source vertex is a ChatVertex
                # thus the target vertex is an external vertex
                # and the source vertex is an input
                target_vertex.has_external_input = True
                self.inputs.append(source_vertex.id)
            if isinstance(target_vertex, ChatVertex):
                # The target vertex is a ChatVertex
                # thus the source vertex is an external vertex
                # and the target vertex is an output
                source_vertex.has_external_output = True
                self.outputs.append(target_vertex.id)

    def remove_vertex(self, vertex_id: str) -> None:
        """Removes a vertex from the graph."""
        vertex = self.get_vertex(vertex_id)
        if vertex is None:
            return
        self.vertices.remove(vertex)
        self.vertex_map.pop(vertex_id)
        self.edges = [
            edge
            for edge in self.edges
            if edge.source_id != vertex_id and edge.target_id != vertex_id
        ]

    def _build_vertex_params(self) -> None:
        """Identifies and handles the LLM vertex within the graph."""
        llm_vertex = None
        for vertex in self.vertices:
            vertex._build_params()
            if isinstance(vertex, LLMVertex):
                llm_vertex = vertex

        if llm_vertex:
            for vertex in self.vertices:
                if isinstance(vertex, ToolkitVertex):
                    vertex.params["llm"] = llm_vertex

    def _validate_vertices(self) -> None:
        """Check that all vertices have edges"""
        if len(self.vertices) == 1:
            return
        for vertex in self.vertices:
            if not self._validate_vertex(vertex):
                raise ValueError(
                    f"{vertex.vertex_type} is not connected to any other components"
                )

    def _validate_vertex(self, vertex: Vertex) -> bool:
        """Validates a vertex."""
        # All vertices that do not have edges are invalid
        return len(self.get_vertex_edges(vertex.id)) > 0

    def get_vertex(self, vertex_id: str) -> Union[None, Vertex]:
        """Returns a vertex by id."""
        try:
            return self.vertex_map.get(vertex_id)
        except KeyError:
            raise ValueError(f"Vertex {vertex_id} not found")

    def get_vertex_edges(self, vertex_id: str) -> List[ContractEdge]:
        """Returns a list of edges for a given vertex."""
        return [
            edge
            for edge in self.edges
            if edge.source_id == vertex_id or edge.target_id == vertex_id
        ]

    def get_vertices_with_target(self, vertex_id: str) -> List[Vertex]:
        """Returns the vertices connected to a vertex."""
        vertices: List[Vertex] = []
        for edge in self.edges:
            if edge.target_id == vertex_id:
                vertex = self.get_vertex(edge.source_id)
                if vertex is None:
                    continue
                vertices.append(vertex)
        return vertices

    async def build(self) -> Chain:
        """Builds the graph."""
        # Get root vertex
        root_vertex = payload.get_root_vertex(self)
        if root_vertex is None:
            raise ValueError("No root vertex found")
        return await root_vertex.build()

    def topological_sort(self) -> List[Vertex]:
        """
        Performs a topological sort of the vertices in the graph.

        Returns:
            List[Vertex]: A list of vertices in topological order.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        # States: 0 = unvisited, 1 = visiting, 2 = visited
        state = {vertex: 0 for vertex in self.vertices}
        sorted_vertices = []

        def dfs(vertex):
            if state[vertex] == 1:
                # We have a cycle
                raise ValueError(
                    "Graph contains a cycle, cannot perform topological sort"
                )
            if state[vertex] == 0:
                state[vertex] = 1
                for edge in vertex.edges:
                    if edge.source_id == vertex.id:
                        dfs(self.get_vertex(edge.target_id))
                state[vertex] = 2
                sorted_vertices.append(vertex)

        # Visit each vertex
        for vertex in self.vertices:
            if state[vertex] == 0:
                dfs(vertex)

        return list(reversed(sorted_vertices))

    def generator_build(self) -> Generator[Vertex, None, None]:
        """Builds each vertex in the graph and yields it."""
        sorted_vertices = self.topological_sort()
        logger.debug("There are %s vertices in the graph", len(sorted_vertices))
        yield from sorted_vertices

    def get_predecessors(self, vertex):
        """Returns the predecessors of a vertex."""
        return [
            self.get_vertex(source_id)
            for source_id in self.predecessor_map.get(vertex.id, [])
        ]

    def get_successors(self, vertex):
        """Returns the successors of a vertex."""
        return [
            self.get_vertex(target_id)
            for target_id in self.successor_map.get(vertex.id, [])
        ]

    def get_vertex_neighbors(self, vertex: Vertex) -> Dict[Vertex, int]:
        """Returns the neighbors of a vertex."""
        neighbors: Dict[Vertex, int] = {}
        for edge in self.edges:
            if edge.source_id == vertex.id:
                neighbor = self.get_vertex(edge.target_id)
                if neighbor is None:
                    continue
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
            elif edge.target_id == vertex.id:
                neighbor = self.get_vertex(edge.source_id)
                if neighbor is None:
                    continue
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
        return neighbors

    def _build_edges(self) -> List[ContractEdge]:
        """Builds the edges of the graph."""
        # Edge takes two vertices as arguments, so we need to build the vertices first
        # and then build the edges
        # if we can't find a vertex, we raise an error

        edges: List[ContractEdge] = []
        for edge in self._edges:
            source = self.get_vertex(edge["source"])
            target = self.get_vertex(edge["target"])
            if source is None:
                raise ValueError(f"Source vertex {edge['source']} not found")
            if target is None:
                raise ValueError(f"Target vertex {edge['target']} not found")
            edges.append(ContractEdge(source, target, edge))
        return edges

    def _get_vertex_class(
        self, node_type: str, node_base_type: str, node_id: str
    ) -> Type[Vertex]:
        """Returns the node class based on the node type."""
        # First we check for the node_base_type
        node_name = node_id.split("-")[0]
        if node_name in ["ChatOutput", "ChatInput"]:
            return ChatVertex
        if node_base_type in lazy_load_vertex_dict.VERTEX_TYPE_MAP:
            return lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_base_type]

        if node_name in lazy_load_vertex_dict.VERTEX_TYPE_MAP:
            return lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_name]

        if node_type in FILE_TOOLS:
            return FileToolVertex
        if node_type in lazy_load_vertex_dict.VERTEX_TYPE_MAP:
            return lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_type]
        return (
            lazy_load_vertex_dict.VERTEX_TYPE_MAP[node_base_type]
            if node_base_type in lazy_load_vertex_dict.VERTEX_TYPE_MAP
            else Vertex
        )

    def _build_vertices(self) -> List[Vertex]:
        """Builds the vertices of the graph."""
        vertices: List[Vertex] = []
        for vertex in self._vertices:
            vertex_data = vertex["data"]
            vertex_type: str = vertex_data["type"]  # type: ignore
            vertex_base_type: str = vertex_data["node"]["template"]["_type"]  # type: ignore

            VertexClass = self._get_vertex_class(
                vertex_type, vertex_base_type, vertex_data["id"]
            )
            vertex_instance = VertexClass(vertex, graph=self)
            vertex_instance.set_top_level(self.top_level_vertices)
            vertices.append(vertex_instance)

        return vertices

    def get_children_by_vertex_type(
        self, vertex: Vertex, vertex_type: str
    ) -> List[Vertex]:
        """Returns the children of a vertex based on the vertex type."""
        children = []
        vertex_types = [vertex.data["type"]]
        if "node" in vertex.data:
            vertex_types += vertex.data["node"]["base_classes"]
        if vertex_type in vertex_types:
            children.append(vertex)
        return children

    def __repr__(self):
        vertex_ids = [vertex.id for vertex in self.vertices]
        edges_repr = "\n".join(
            [f"{edge.source_id} --> {edge.target_id}" for edge in self.edges]
        )
        return f"Graph:\nNodes: {vertex_ids}\nConnections:\n{edges_repr}"

    def sort_up_to_vertex(self, vertex_id: str) -> "Graph":
        """Cuts the graph up to a given vertex and sorts the resulting subgraph."""
        # Initial setup
        visited = set()  # To keep track of visited vertices
        stack = [vertex_id]  # Use a list as a stack for DFS

        # DFS to collect all vertices that can reach the specified vertex
        while stack:
            current_id = stack.pop()
            if current_id not in visited:
                visited.add(current_id)
                current_vertex = self.get_vertex(current_id)
                # Assuming get_predecessors is a method that returns all vertices with edges to current_vertex
                for predecessor in current_vertex.predecessors:
                    stack.append(predecessor.id)

        # Filter the original graph's vertices and edges to keep only those in `visited`
        vertices_to_keep = [self.get_vertex(vid) for vid in visited]

        return vertices_to_keep

    def layered_topological_sort(
        self,
        vertices: List[Vertex],
    ) -> List[List[str]]:
        """Performs a layered topological sort of the vertices in the graph."""

        # Queue for vertices with no incoming edges
        queue = deque(
            vertex.id for vertex in vertices if self.in_degree_map[vertex.id] == 0
        )
        layers = []

        current_layer = 0
        while queue:
            layers.append([])  # Start a new layer
            layer_size = len(queue)
            for _ in range(layer_size):
                vertex_id = queue.popleft()
                layers[current_layer].append(vertex_id)
                for neighbor in self.successor_map[vertex_id]:
                    self.in_degree_map[neighbor] -= 1  # 'remove' edge
                    if self.in_degree_map[neighbor] == 0:
                        queue.append(neighbor)
            current_layer += 1  # Next layer
        new_layers = self.refine_layers(layers)
        return new_layers

    def refine_layers(self, initial_layers):
        # Map each vertex to its current layer
        vertex_to_layer = {}
        for layer_index, layer in enumerate(initial_layers):
            for vertex in layer:
                vertex_to_layer[vertex] = layer_index

        # Build the adjacency list for reverse lookup (dependencies)

        refined_layers = [[] for _ in initial_layers]  # Start with empty layers
        new_layer_index_map = defaultdict(int)

        # Map each vertex to its new layer index
        # by finding the lowest layer index of its dependencies
        # and subtracting 1
        # If a vertex has no dependencies, it will be placed in the first layer
        # If a vertex has dependencies, it will be placed in the lowest layer index of its dependencies
        # minus 1
        for vertex_id, deps in self.successor_map.items():
            indexes = [vertex_to_layer[dep] for dep in deps]
            new_layer_index = max(min(indexes, default=0) - 1, 0)
            new_layer_index_map[vertex_id] = new_layer_index

        for layer_index, layer in enumerate(initial_layers):
            for vertex_id in layer:
                # Place the vertex in the highest possible layer where its dependencies are met
                new_layer_index = new_layer_index_map[vertex_id]
                if new_layer_index > layer_index:
                    refined_layers[new_layer_index].append(vertex_id)
                    vertex_to_layer[vertex_id] = new_layer_index
                else:
                    refined_layers[layer_index].append(vertex_id)

        # Remove empty layers if any
        refined_layers = [layer for layer in refined_layers if layer]

        return refined_layers

    def sort_chat_inputs_first(self, vertices: List[List[str]]) -> List[List[str]]:

        chat_inputs_first = []
        for layer in vertices:
            for vertex_id in layer:
                if "ChatInput" in vertex_id:
                    # Remove the ChatInput from the layer
                    layer.remove(vertex_id)
                    chat_inputs_first.append(vertex_id)
        if not chat_inputs_first:
            return vertices

        vertices = [chat_inputs_first] + vertices

        return vertices

    def sort_vertices(self, component_id: Optional[str] = None) -> List[List[str]]:
        """Sorts the vertices in the graph."""
        if component_id:
            vertices = self.sort_up_to_vertex(component_id)
        else:
            vertices = self.vertices
        vertices = self.layered_topological_sort(vertices)
        vertices = self.sort_interface_components_first(vertices)
        vertices = self.sort_chat_inputs_first(vertices)
        self.increment_run_count()
        return vertices

    def sort_interface_components_first(self, vertices: List[Vertex]) -> List[Vertex]:
        """Sorts the vertices in the graph so that vertices containing ChatInput or ChatOutput come first."""

        def contains_interface_component(vertex):
            return any(
                component.value in vertex for component in InterfaceComponentTypes
            )

        # Sort each inner list so that vertices containing ChatInput or ChatOutput come first
        sorted_vertices = [
            sorted(
                inner_list,
                key=lambda vertex: not contains_interface_component(vertex),
            )
            for inner_list in vertices
        ]
        return sorted_vertices
