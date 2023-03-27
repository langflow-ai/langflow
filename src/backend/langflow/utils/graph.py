import types
from typing import Dict, List, Union
from langflow.interface import loading
from langflow.utils import payload, util
from langflow.interface.listing import ALL_TYPES_DICT


class Node:
    def __init__(self, data: Dict):
        self.id: str = data["id"]
        self._data = data
        self.edges: List[Edge] = []
        self._parse_data()

    def _parse_data(self) -> None:
        self.data = self._data["data"]
        self.output = self.data["node"]["base_classes"]
        template_dicts = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }

        self.required_inputs = [
            template_dicts[key]["type"]
            for key, value in template_dicts.items()
            if value["required"]
        ]
        self.optional_inputs = [
            template_dicts[key]["type"]
            for key, value in template_dicts.items()
            if not value["required"]
        ]

        template_dict = self.data["node"]["template"]
        self.node_type = (
            self.data["type"] if "Tool" not in self.output else template_dict["_type"]
        )

    def _build_params(self):
        # Some params are required, some are optional
        # but most importantly, some params are python base classes
        # like str and others are LangChain objects like LLMChain, BasePromptTemplate
        # so we need to be able to distinguish between the two

        # The dicts with "type" == "str" are the ones that are python base classes
        # and most likely have a "value" key

        # So for each key besides "_type" in the template dict, we have a dict
        # with a "type" key. If the type is not "str", then we need to get the
        # edge that connects to that node and get the Node with the required data
        # and use that as the value for the param
        # If the type is "str", then we need to get the value of the "value" key
        # and use that as the value for the param
        template_dict = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }
        params = {}
        for key, value in template_dict.items():
            if key == "_type":
                continue
            if value["type"] not in ["str", "bool"]:
                # Get the edge that connects to this node
                edge = next(
                    (
                        edge
                        for edge in self.edges
                        if edge.target == self and edge.matched_type in value["type"]
                    ),
                    None,
                )
                # Get the output of the node that the edge connects to
                # if the value['list'] is True, then there will be more
                # than one time setting to params[key]
                # so we need to append to a list if it exists
                # or create a new list if it doesn't
                if edge is None and value["required"]:
                    # break line
                    raise ValueError(
                        f"Required input {key} for module {self.node_type} not found"
                    )
                if value["list"]:
                    if key in params:
                        params[key].append(edge.source)
                    else:
                        params[key] = [edge.source]
                elif value["required"] or edge is not None:
                    params[key] = edge.source
            elif value["required"] or value.get("value"):
                params[key] = value["value"]

        # Add _type to params
        self.params = params

    def build(self):
        # The params dict is used to build the module
        # it contains values and keys that point to nodes which
        # have their own params dict
        # When build is called, we iterate through the params dict
        # and if the value is a node, we call build on that node
        # and use the output of that build as the value for the param
        # if the value is not a node, then we use the value as the param
        # and continue
        # Another aspect is that the node_type is the class that we need to import
        # and instantiate with these built params

        # Build each node in the params dict
        for key, value in self.params.items():
            # Check if Node or list of Nodes
            if isinstance(value, Node):
                result = value.build()
                # If the key is "func", then we need to use the run method
                if key == "func" and not isinstance(result, types.FunctionType):
                    result = result.run
                self.params[key] = result
            elif isinstance(value, list) and all(
                isinstance(node, Node) for node in value
            ):
                self.params[key] = [node.build() for node in value]  # type: ignore

        # Get the class from LANGCHAIN_TYPES_DICT
        # and instantiate it with the params
        # and return the instance
        instance = None
        for base_type, value in ALL_TYPES_DICT.items():
            if base_type == "tools":
                value = util.get_tools_dict()

            if self.node_type in value:
                instance = loading.instantiate_class(
                    node_type=self.node_type,
                    base_type=base_type,
                    params=self.params,
                )
                break
        return instance

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
        # Validate that the outputs of the source node are valid inputs
        # for the target node
        self.source_types = self.source.output
        self.target_reqs = self.target.required_inputs + self.target.optional_inputs
        # Both lists contain strings and sometimes a string contains the value we are
        # looking for e.g. comgin_out=["Chain"] and target_reqs=["LLMChain"]
        # so we need to check if any of the strings in source_types is in target_reqs
        self.valid = any(
            output in target_req
            for output in self.source_types
            for target_req in self.target_reqs
        )
        # Get what type of input the target node is expecting

        self.matched_type = next(
            (
                output
                for output in self.source_types
                for target_req in self.target_reqs
                if output in target_req
            ),
            None,
        )

    def __repr__(self) -> str:
        return (
            f"Edge(source={self.source.id}, target={self.target.id}, valid={self.valid}"
            f", matched_type={self.matched_type})"
        )


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

        for node in self.nodes:
            node._build_params()

    def get_node(self, node_id: str) -> Union[None, Node]:
        return next((node for node in self.nodes if node.id == node_id), None)

    def get_nodes_with_target(self, node: Node) -> List[Node]:
        connected_nodes: List[Node] = [
            edge.source for edge in self.edges if edge.target == node
        ]
        return connected_nodes

    def build(self) -> List[Node]:
        # Get root node
        root_node = payload.get_root_node(self)
        return root_node.build()

    def get_node_neighbors(self, node: Node) -> Dict[Node, int]:
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

    def get_children_by_node_type(self, node: Node, node_type: str) -> List[Node]:
        children = []
        node_types = [node.data["type"]]
        if "node" in node.data:
            node_types += node.data["node"]["base_classes"]
        if node_type in node_types:
            children.append(node)
        return children
