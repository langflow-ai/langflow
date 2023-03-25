from typing import Dict, List, Union
from langflow.interface import listing
from langflow.interface.importing import import_by_type
from langflow.utils import payload, util

LANGCHAIN_TYPES_DICT = {
    k: list_function() for k, list_function in listing.get_type_dict().items()
}


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
        self.module_type = (
            self.data["type"] if "Tool" not in self.output else template_dict["_type"]
        )

    def _build_params(self) -> Dict:
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
                    raise ValueError(
                        f"Required input {key} for module {self.module_type} is not connected"
                    )
                if value["list"]:
                    if key in params:
                        params[key].append(edge.source)
                    else:
                        params[key] = [edge.source]
                else:
                    if not value["required"] and edge is None:
                        continue

                    params[key] = edge.source
            else:
                if not value["required"] and not value.get("value"):
                    continue
                params[key] = value["value"]

        # Add _type to params
        self.params = params

    def build(self):
        from langflow.interface.loading import load_agent_executor

        # The params dict is used to build the module
        # it contains values and keys that point to nodes which
        # have their own params dict
        # When build is called, we iterate through the params dict
        # and if the value is a node, we call build on that node
        # and use the output of that build as the value for the param
        # if the value is not a node, then we use the value as the param
        # and continue
        # Another aspect is that the module_type is the class that we need to import
        # and instantiate with these built params

        # Build each node in the params dict
        for key, value in self.params.items():
            # Check if Node or list of Nodes
            if isinstance(value, Node):
                self.params[key] = value.build()

            elif isinstance(value, list) and all(
                isinstance(node, Node) for node in value
            ):
                self.params[key] = [node.build() for node in value]  # type: ignore

        # Get the class from LANGCHAIN_TYPES_DICT
        # and instantiate it with the params
        # and return the instance
        instance = None
        for key, value in LANGCHAIN_TYPES_DICT.items():
            if key == "tools":
                value = util.get_tools_dict()
            if self.module_type in value:
                class_object = import_by_type(_type=key, name=self.module_type)
                if key == "agents":
                    # We need to initialize it differently
                    allowed_tools = self.params["allowed_tools"]
                    llm_chain = self.params["llm_chain"]
                    instance = load_agent_executor(
                        class_object, allowed_tools, llm_chain
                    )
                elif key == "tools":
                    instance = class_object(**self.params)
                elif self.module_type == "ZeroShotPrompt":
                    from langchain.agents import ZeroShotAgent

                    instance = ZeroShotAgent.create_prompt(**self.params, tools=[])
                else:
                    instance = class_object(**self.params)
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
        # Validate that the outputs of the source node are valid inputs for the target node
        self.source_types = self.source.output
        self.target_reqs = self.target.required_inputs + self.target.optional_inputs
        # Both lists contain strings and sometimes a string contains the value we are looking for
        # e.g. comgin_out=["Chain"] and target_reqs=["LLMChain"]
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
