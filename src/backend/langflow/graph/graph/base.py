from typing import Dict, Generator, List, Optional, Tuple, Type, Union

from langflow.graph import Edge, Vertex
from langflow.graph.edge.contract import ContractEdge
from langflow.graph.graph.constants import VERTEX_TYPE_MAP
from langflow.graph.vertex.types import (
    FileToolVertex,
    LLMVertex,
    ToolkitVertex,
)
from langflow.graph.vertex.types import ConnectorVertex
from langflow.interface.tools.constants import FILE_TOOLS
from langflow.utils import payload
from langflow.utils.logger import logger
from langchain.chains.base import Chain


class Graph:
    def __init__(
        self,
        *,
        graph_data: Optional[Dict] = None,
        vertices: Optional[List[Vertex]] = None,
        edges: Optional[List[Edge]] = None,
    ) -> None:
        self.has_connectors = False

        if graph_data:
            _nodes = graph_data["nodes"]
            _edges = graph_data["edges"]
            self._nodes = _nodes
            self._edges = _edges
            self.vertices = []
            self.edges = []
            self._build_vertices_and_edges()
        elif vertices and edges:
            self.vertices = vertices
            self.edges = edges

    @classmethod
    def from_root_vertex(cls, root_vertex: Vertex):
        # Starting at the root vertex
        # Iterate all of its edges to find
        # all vertices and edges
        vertices, edges = cls.traverse_graph(root_vertex)
        return cls(vertices=vertices, edges=edges)

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
            nodes = payload["nodes"]
            edges = payload["edges"]
            return cls(vertices=nodes, edges=edges)
        except KeyError as exc:
            raise ValueError(
                f"Invalid payload. Expected keys 'nodes' and 'edges'. Found {list(payload.keys())}"
            ) from exc

    @staticmethod
    def traverse_graph(root_vertex: Vertex) -> Tuple[List[Vertex], List[Edge]]:
        """
        Traverses the graph from the root_vertex using depth-first search (DFS) and returns all the vertices and edges.

        Args:
            root_vertex (Vertex): The root vertex to start traversal from.

        Returns:
            tuple: A tuple containing a set of all vertices and all edges visited in the graph.
        """
        # Initialize empty sets for visited vertices and edges.
        visited_vertices = set()
        visited_edges = set()

        # Initialize a stack with the root vertex.
        stack = [root_vertex]

        # Continue while there are vertices to be visited in the stack.
        while stack:
            # Pop a vertex from the stack.
            vertex = stack.pop()

            # If this vertex has not been visited, add it to visited_vertices.
            if vertex not in visited_vertices:
                visited_vertices.add(vertex)

                # Iterate over the edges of the current vertex.
                for edge in vertex.edges:
                    # If this edge has not been visited, add it to visited_edges.
                    if edge not in visited_edges:
                        visited_edges.add(edge)

                        # Add the adjacent vertex (the one that's not the current vertex)
                        #  to the stack for future exploration.
                        stack.append(
                            edge.source if edge.source != vertex else edge.target
                        )

        # Return the sets of visited vertices and edges.
        return list(visited_vertices), list(visited_edges)

    def _build_vertices_and_edges(self) -> None:
        self.vertices += self._build_vertices()
        self.edges += self._build_edges()
        for edge in self.edges:
            try:
                edge.source.add_edge(edge)
                edge.target.add_edge(edge)
            except AttributeError as e:
                print(e)
        # This is a hack to make sure that the LLM vertex is sent to
        # the toolkit vertex
        llm_vertex = None
        for vertex in self.vertices:
            vertex._build_params()

            if isinstance(vertex, LLMVertex):
                llm_vertex = vertex

        for vertex in self.vertices:
            if isinstance(vertex, ToolkitVertex):
                vertex.params["llm"] = llm_vertex
        # remove invalid vertices
        self.vertices = [
            vertex
            for vertex in self.vertices
            if self._validate_vertex(vertex)
            or (len(self.vertices) == 1 and len(self.edges) == 0)
        ]

    def _validate_vertex(self, vertex: Vertex) -> bool:
        # All vertices that do not have edges are invalid
        return len(vertex.edges) > 0

    def get_vertex(self, vertex_id: str) -> Union[None, Vertex]:
        return next(
            (vertex for vertex in self.vertices if vertex.id == vertex_id), None
        )

    def get_vertices_with_target(self, vertex: Vertex) -> List[Vertex]:
        connected_vertices: List[Vertex] = [
            edge.source for edge in self.edges if edge.target == vertex
        ]
        return connected_vertices

    def build(self) -> Chain:
        """Builds the graph."""
        # Get root node
        root_node = payload.get_root_vertex(self)
        if root_node is None:
            raise ValueError("No root node found")
        return root_node.build()

    def topological_sort(self) -> List[Vertex]:
        """
        Performs a topological sort of the vertices in the graph.

        Returns:
            List[Vertex]: A list of vertices in topological order.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        # States: 0 = unvisited, 1 = visiting, 2 = visited
        state = {node: 0 for node in self.vertices}
        sorted_vertices = []

        def dfs(node):
            if state[node] == 1:
                # We have a cycle
                raise ValueError(
                    "Graph contains a cycle, cannot perform topological sort"
                )
            if state[node] == 0:
                state[node] = 1
                for edge in node.edges:
                    if edge.source == node:
                        dfs(edge.target)
                state[node] = 2
                sorted_vertices.append(node)

        # Visit each node
        for node in self.vertices:
            if state[node] == 0:
                dfs(node)

        return list(reversed(sorted_vertices))

    def generator_build(self) -> Generator:
        """Builds each vertex in the graph and yields it."""
        sorted_vertices = self.topological_sort()
        logger.info("Sorted vertices: %s", sorted_vertices)
        yield from sorted_vertices

    def get_node_neighbors(self, vertex: Vertex) -> Dict[Vertex, int]:
        """Returns the neighbors of a node."""
        neighbors: Dict[Vertex, int] = {}
        for edge in self.edges:
            if edge.source == vertex:
                neighbor = edge.target
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
            elif edge.target == vertex:
                neighbor = edge.source
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
        return neighbors

    def _build_edges(self) -> List[ContractEdge]:
        # Edge takes two vertices as arguments, so we need to build the vertices first
        # and then build the edges
        # if we can't find a vertex, we raise an error

        edges: List[ContractEdge] = []
        for raw_edge in self._edges:
            source = self.get_vertex(raw_edge["source"])
            target = self.get_vertex(raw_edge["target"])
            if source is None:
                raise ValueError(f"Source vertex {raw_edge['source']} not found")
            if target is None:
                raise ValueError(f"Target vertex {raw_edge['target']} not found")
            edges.append(ContractEdge(source, target, raw_edge))
        return edges

    def _get_vertex_class(self, vertex_type: str, vertex_lc_type: str) -> Type[Vertex]:
        if vertex_type in FILE_TOOLS:
            return FileToolVertex
        vertex_class = VERTEX_TYPE_MAP.get(vertex_type)
        if vertex_class is None:
            vertex_class = VERTEX_TYPE_MAP.get(vertex_lc_type, Vertex)

        return vertex_class

    def _build_vertices(self) -> List[Vertex]:
        vertices: List[Vertex] = []

        self.expand_flow_vertices(self._nodes)
        for vertex in self._nodes:
            vertex_data = vertex["data"]
            vertex_type: str = vertex_data["type"]  # type: ignore
            if vertex_type == "flow":
                continue
            vertex_lc_type: str = vertex_data["node"]["template"].get("_type")  # type: ignore

            # Some vertices are a bit special and need to be handled differently
            # vertex_type is "flow" and vertex_data["node"] contains a "flow" key which
            # is itself a graph.

            VertexClass = self._get_vertex_class(vertex_type, vertex_lc_type)
            vertices.append(VertexClass(vertex))
            if VertexClass == ConnectorVertex:
                self.has_connectors = True

        return vertices

    def expand_flow_vertices(self, vertices: list):
        # Certain vertices are actually graphs themselves, so we need to expand them
        # and add their vertices and edges to the current graph
        # The problem is that the vertex has an id, and the inner vertices also have an id
        # and the edges also have an id
        # The id is what is used to connect the vertices and edges together
        # So the vertex id needs to replace the inner vertex id for the vertex that has
        # has a root_field in the ["node"]["template"] dict
        # The edges need to be updated to use the new vertex id
        # The inner vertices need to be updated to use the new vertex id
        for vertex in vertices.copy():
            vertex_data = vertex["data"]["node"]
            if "flow" in vertex_data:
                self.expand_flow_vertex(vertex)
                vertices.remove(vertex)

    def expand_flow_vertex(self, flow_vertex):
        # Get the subgraph data from the flow vertex
        subgraph_data = flow_vertex["data"]["node"]["flow"]["data"]

        # Build the subgraph Graph object
        subgraph = Graph(graph_data=subgraph_data)

        # Set the ID of the subgraph root vertex to the flow vertex ID
        subgraph_root = payload.get_root_vertex(subgraph)
        old_id = subgraph_root.id
        if subgraph_root is None:
            raise ValueError("No root vertex found")
        subgraph_root.id = flow_vertex["id"]

        # Get all edges in the subgraph graph that have the subgraph root as the source or target
        edges_to_update = [
            edge
            for edge in subgraph.edges
            if edge.source == subgraph_root or edge.target == subgraph_root
        ]

        # Update all such edges to use the flow vertex ID instead
        for edge in edges_to_update:
            # The root vertex shouldn't be the source of any edges, but just in case
            if edge.source.id == old_id:
                edge.source = subgraph_root
            if edge.target.id == old_id:
                edge.target = subgraph_root

        # Add subgraph vertices and edges to the main graph
        self.vertices.extend(subgraph.vertices)
        self.edges.extend(subgraph.edges)

    def get_children_by_vertex_type(
        self, vertex: Vertex, vertex_type: str
    ) -> List[Vertex]:
        children = []
        vertex_types = [vertex.data["type"]]
        if "node" in vertex.data:
            vertex_types += vertex.data["node"]["base_classes"]
        if vertex_type in vertex_types:
            children.append(vertex)
        return children

    def __hash__(self):
        vertices_hash = hash(tuple(self.vertices))
        edges_hash = hash(tuple(self.edges))
        return hash((vertices_hash, edges_hash))

    def __eq__(self, other):
        if isinstance(other, Graph):
            return self.vertices == other.vertices and self.edges == other.edges
        return False
