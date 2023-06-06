from typing import Dict, List, Type, Union

from langflow.graph.edge.base import Edge
from langflow.graph.graph.constants import VERTEX_TYPE_MAP
from langflow.graph.vertex.base import Vertex
from langflow.graph.vertex.types import (
    FileToolVertex,
    LLMVertex,
    ToolkitVertex,
)
from langflow.interface.tools.constants import FILE_TOOLS
from langflow.utils import payload


class Graph:
    """A class representing a graph of nodes and edges."""

    def __init__(
        self,
        nodes: List[Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]],
        edges: List[Dict[str, str]],
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._build_graph()

    @classmethod
    @classmethod
    def from_payload(cls, payload: Dict) -> "Graph":
        """
        Creates a graph from a payload.

        Args:
            payload (Dict): The payload to create the graph from.

        Returns:
            Graph: The created graph.
        """
        if "data" in payload:
            payload = payload["data"]
        try:
            nodes = payload["nodes"]
            edges = payload["edges"]
            return cls(nodes, edges)
        except KeyError as exc:
            raise ValueError("Invalid payload") from exc

    def _build_graph(self) -> None:
        """Builds the graph from the nodes and edges."""
        self.nodes = self._build_vertices()
        self.edges = self._build_edges()
        for edge in self.edges:
            edge.source.add_edge(edge)
            edge.target.add_edge(edge)

        # This is a hack to make sure that the LLM node is sent to
        # the toolkit node
        self._build_node_params()
        # remove invalid nodes
        self._remove_invalid_nodes()

    def _build_node_params(self) -> None:
        """Identifies and handles the LLM node within the graph."""
        llm_node = None
        for node in self.nodes:
            node._build_params()
            if isinstance(node, LLMVertex):
                llm_node = node

        if llm_node:
            for node in self.nodes:
                if isinstance(node, ToolkitVertex):
                    node.params["llm"] = llm_node

    def _remove_invalid_nodes(self) -> None:
        """Removes invalid nodes from the graph."""
        self.nodes = [
            node
            for node in self.nodes
            if self._validate_node(node)
            or (len(self.nodes) == 1 and len(self.edges) == 0)
        ]

    def _validate_node(self, node: Vertex) -> bool:
        """Validates a node."""
        # All nodes that do not have edges are invalid
        return len(node.edges) > 0

    def get_node(self, node_id: str) -> Union[None, Vertex]:
        """Returns a node by id."""
        return next((node for node in self.nodes if node.id == node_id), None)

    def get_nodes_with_target(self, node: Vertex) -> List[Vertex]:
        """Returns the nodes connected to a node."""
        connected_nodes: List[Vertex] = [
            edge.source for edge in self.edges if edge.target == node
        ]
        return connected_nodes

    def build(self) -> List[Vertex]:
        """Builds the graph."""
        # Get root node
        root_node = payload.get_root_node(self)
        if root_node is None:
            raise ValueError("No root node found")
        return root_node.build()

    def get_node_neighbors(self, node: Vertex) -> Dict[Vertex, int]:
        """Returns the neighbors of a node."""
        neighbors: Dict[Vertex, int] = {}
        for edge in self.edges:
            if edge.source == node:
                neighbor = edge.target
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
            elif edge.target == node:
                neighbor = edge.source
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
        return neighbors

    def _build_edges(self) -> List[Edge]:
        """Builds the edges of the graph."""
        # Edge takes two nodes as arguments, so we need to build the nodes first
        # and then build the edges
        # if we can't find a node, we raise an error

        edges: List[Edge] = []
        for edge in self._edges:
            source = self.get_node(edge["source"])
            target = self.get_node(edge["target"])
            if source is None:
                raise ValueError(f"Source node {edge['source']} not found")
            if target is None:
                raise ValueError(f"Target node {edge['target']} not found")
            edges.append(Edge(source, target))
        return edges

    def _get_vertex_class(self, node_type: str, node_lc_type: str) -> Type[Vertex]:
        """Returns the node class based on the node type."""
        if node_type in FILE_TOOLS:
            return FileToolVertex
        if node_type in VERTEX_TYPE_MAP:
            return VERTEX_TYPE_MAP[node_type]
        return (
            VERTEX_TYPE_MAP[node_lc_type] if node_lc_type in VERTEX_TYPE_MAP else Vertex
        )

    def _build_vertices(self) -> List[Vertex]:
        """Builds the vertices of the graph."""
        nodes: List[Vertex] = []
        for node in self._nodes:
            node_data = node["data"]
            node_type: str = node_data["type"]  # type: ignore
            node_lc_type: str = node_data["node"]["template"]["_type"]  # type: ignore

            VertexClass = self._get_vertex_class(node_type, node_lc_type)
            nodes.append(VertexClass(node))

        return nodes

    def get_children_by_node_type(self, node: Vertex, node_type: str) -> List[Vertex]:
        """Returns the children of a node based on the node type."""
        children = []
        node_types = [node.data["type"]]
        if "node" in node.data:
            node_types += node.data["node"]["base_classes"]
        if node_type in node_types:
            children.append(node)
        return children
