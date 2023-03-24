from typing import Dict, List, Union


class Node:
    def __init__(self, data: Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]):
        self.id: str = data["id"]
        self._data = data
        self.edges: List[Edge] = []
        self._parse_data()

    def _parse_data(self) -> None:
        self.data = self._data["data"]

    def add_edge(self, edge: "Edge") -> None:
        self.edges.append(edge)

    def __repr__(self) -> str:
        return f"Node(id={self.id}, data={self.data})"

    def __eq__(self, __o: object) -> bool:
        return self.id == __o.id if isinstance(__o, Node) else False

    def __hash__(self) -> int:
        return id(self)


class Edge:
    def __init__(self, source: "Node", target: "Node"):
        self.source: "Node" = source
        self.target: "Node" = target

    def __repr__(self) -> str:
        return f"Edge(source={self.source.id}, target={self.target.id})"


class Graph:
    def __init__(
        self,
        nodes: List[Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]],
        edges: List[Dict[str, str]],
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._build_graph()

    def _build_graph(self) -> None:
        self.nodes = self._build_nodes()
        self.edges = self._build_edges()
        for edge in self.edges:
            edge.source.add_edge(edge)
            edge.target.add_edge(edge)

    def get_node(self, node_id: str) -> Union[None, Node]:
        return next((node for node in self.nodes if node.id == node_id), None)

    def get_connected_nodes(self, node_id: str) -> List[Node]:
        connected_nodes: List[Node] = []
        for edge in self.edges:
            if edge.source.id == node_id:
                connected_nodes.append(edge.target)
            elif edge.target.id == node_id:
                connected_nodes.append(edge.source)
        return connected_nodes

    def get_node_neighbors(self, node_id: str) -> Dict[str, int]:
        neighbors: Dict[str, int] = {}
        for edge in self.edges:
            if edge.source.id == node_id:
                neighbor_id = edge.target.id
                if neighbor_id not in neighbors:
                    neighbors[neighbor_id] = 0
                neighbors[neighbor_id] += 1
            elif edge.target.id == node_id:
                neighbor_id = edge.source.id
                if neighbor_id not in neighbors:
                    neighbors[neighbor_id] = 0
                neighbors[neighbor_id] += 1
        return neighbors

    def _build_edges(self) -> List[Edge]:
        return [
            Edge(self.get_node(edge["source"]), self.get_node(edge["target"]))
            for edge in self._edges
        ]

    def _build_nodes(self) -> List[Node]:
        return [Node(node) for node in self._nodes]
