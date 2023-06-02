from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

from langflow.cache.base import memoize_dict
from langflow.graph import Node
from langflow.graph import Graph
from langflow.graph.node.types import LangChainNode
from langflow.graph.node.types import ConnectorNode
from langflow.interface.run import get_result_and_steps


class GraphMap:
    def __init__(self, graph_data: Dict, is_first_message: bool) -> None:
        self.graph_data = graph_data
        if is_first_message:
            self._build_elements.clear_cache()
        self.graph, self.elements = GraphMap._build_elements(graph_data)
        self.intermediate_steps: List[str] = []
        self.node_cache: Dict[Union[Node, "ConnectorNode"], Any] = {}
        self.last_node: Optional[Union[Node, "ConnectorNode"]] = None

    async def process(self, input: str, **kwargs) -> Tuple[str, str]:
        result = input
        built_object = None
        self.results = []
        for element in self.elements:
            # If the element is the same as the last one, reuse the cached result
            if element == self.last_node:
                result = self.node_cache[element]
            else:
                # Build the graph or connector node and get the root node
                built_object = element.build()
                # check if it is a
                if isinstance(element, LangChainNode):
                    # result must be a str
                    result = str(result)
                    result, steps = await get_result_and_steps(
                        built_object, result, **kwargs
                    )
                    self.intermediate_steps.append(steps)
                else:
                    result = built_object(result)
                # Store the result in the cache
                self.node_cache[element] = result
                # Update the last node
                self.last_node = element
                self.results.append((element.base_type, result))
        # str(result) is a temporary solution
        return str(result), "\n".join(self.intermediate_steps)

    @memoize_dict(maxsize=20)
    @staticmethod
    def _build_elements(
        graph_data: Dict,
    ) -> Tuple[Graph, List[Union[Node, ConnectorNode]]]:
        graph = Graph(graph_data=graph_data)
        graph_copy = deepcopy(graph)
        elements: List[Node] = []

        current_root = graph.root_node
        while current_root:
            if current_root.can_be_root:
                graph.nodes.remove(current_root)
                edges_to_remove = [
                    edge
                    for edge in graph.edges
                    if edge.source == current_root or edge.target == current_root
                ]
                for edge in edges_to_remove:
                    graph.edges.remove(edge)
                for node in graph.nodes:
                    node.edges = [
                        edge
                        for edge in node.edges
                        if edge.source != current_root and edge.target != current_root
                    ]
                elements.insert(0, current_root)
                current_root = graph.root_node
            else:
                current_root = next(
                    (node for node in graph.nodes if node.can_be_root), None
                )
        # Build elements to cache built objects
        for element in elements:
            # Build the element but keep the node instead of the object
            element.build()
        return graph_copy, elements
