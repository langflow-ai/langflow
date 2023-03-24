from typing import Dict, List, Union


class Node:
    def __init__(self, data: Dict):
        self.id: str = data["id"]
        self._data = data
        self.edges: List[Edge] = []
        self._parse_data()

    def _parse_data(self) -> None:
        self.data = self._data["data"]
        # Data dict:
        # {'type': 'LLMChain', 'node': {'template': {'_type': 'llm_chain', 'memory': {'type': 'BaseMemory', 'required': False, 'placeholder': '', 'list': False, 'show': True, 'password': False, 'multiline': False, 'value': None}, 'verbose': {'type': 'bool', 'required': False, 'placeholder': '', 'list': False, 'show': False, 'password': False, 'multiline': False, 'value': False}, 'prompt': {'type': 'BasePromptTemplate', 'required': True, 'placeholder': '', 'list': False, 'show': True, 'password': False, 'multiline': False}, 'llm': {'type': 'BaseLanguageModel', 'required': True, 'placeholder': '', 'list': False, 'show': True, 'password': False, 'multiline': False}, 'output_key': {'type': 'str', 'required': False, 'placeholder': '', 'list': False, 'show': False, 'password': True, 'multiline': False, 'value': 'text'}}, 'description': 'Chain to run queries against LLMs.', 'base_classes': ['Chain']}, 'id': 'dndnode_1', 'value': None}
        # base_classes are the classes that the node can be cast to
        self.output = self.data["node"]["base_classes"]
        template_dict = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }

        self.required_inputs = [
            template_dict[key]["type"]
            for key, value in template_dict.items()
            if value["required"]
        ]
        self.optional_inputs = [
            template_dict[key]["type"]
            for key, value in template_dict.items()
            if not value["required"]
        ]

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
        self.validate_edge()

    def validate_edge(self) -> None:
        # Validate that the outputs of the source node are valid inputs for the target node
        self.coming_out = self.source.output
        self.going_in = self.target.required_inputs + self.target.optional_inputs
        # Both lists contain strings and sometimes a string contains the value we are looking for
        # e.g. comgin_out=["Chain"] and going_in=["LLMChain"]
        # so we need to check if any of the strings in coming_out is in going_in
        self.valid = any(
            output in going_in
            for output in self.coming_out
            for going_in in self.going_in
        )

    def __repr__(self) -> str:
        return f"Edge(source={self.source.id}, target={self.target.id}, valid={self.valid}, coming_out={self.coming_out}, going_in={self.going_in})"


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

    def get_nodes_with_target(self, node: Node) -> List[Node]:
        connected_nodes: List[Node] = [
            edge.source for edge in self.edges if edge.target == node
        ]
        return connected_nodes

    def get_node_neighbors(self, node: Node) -> Dict[str, int]:
        neighbors: Dict[Node, int] = {}
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

    def _build_nodes(self) -> List[Node]:
        return [Node(node) for node in self._nodes]

    def get_children_by_module_type(self, node: Node, module_type: str) -> List[Node]:
        children = []
        module_types = [node.data["type"]]
        if "node" in node.data:
            module_types += node.data["node"]["base_classes"]
        if module_type in module_types:
            children.append(node)
        return children
