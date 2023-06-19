# Path: src/backend/langflow/graph/graph_map.py
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

from langflow.cache.utils import memoize_dict
from langflow.graph import Vertex
from langflow.graph import Graph
from langflow.graph.vertex.types import ConnectorVertex
from collections import deque
from langflow.graph.schema import Message


class GraphMap:
    def __init__(self, graph_data: Dict, is_first_message: bool) -> None:
        self.graph_data = graph_data
        if is_first_message:
            self._build_elements.clear_cache()
        self.graph, self.sorted_vertices = GraphMap._build_elements(graph_data)
        self.intermediate_steps: List[str] = []
        self.node_cache: Dict[Union[Vertex, "ConnectorVertex"], Any] = {}
        self.last_node: Optional[Union[Vertex, "ConnectorVertex"]] = None

    # async def process(self, input: str, **kwargs) -> Tuple[str, str]:
    #     result = input
    #     built_object = None
    #     self.results = []
    #     for element in self.runnable_elements:
    #         # If the element is the same as the last one, reuse the cached result
    #         if element == self.last_node:
    #             result = self.node_cache[element]
    #         else:
    #             # Build the graph or connector node and get the root node
    #             built_object = element.build()
    #             # check if it is a
    #             if isinstance(element, LangChainVertex):
    #                 # result must be a str
    #                 result = str(result)
    #                 result, steps = await get_result_and_steps(
    #                     built_object, result, **kwargs
    #                 )
    #                 self.intermediate_steps.append(steps)
    #             else:
    #                 result = built_object(result)
    #             # Store the result in the cache
    #             self.node_cache[element] = result
    #             # Update the last node
    #             self.last_node = element
    #             self.results.append((element.base_type, result))
    #     # str(result) is a temporary solution
    #     return str(result), "\n".join(self.intermediate_steps)

    def process(self, input_data: str, **kwargs):
        message = Message(text=input_data)
        for vertex in self.sorted_vertices:
            for edge in vertex.edges:
                edge.fulfill(message)

    @memoize_dict(maxsize=20)
    @staticmethod
    def _build_elements(
        graph_data: Dict,
    ) -> Tuple[Graph, List[Union[Vertex, ConnectorVertex]]]:
        graph = Graph(graph_data=graph_data)
        graph_copy = deepcopy(graph)
        sorted_vertices = GraphMap.topological_sort(graph)

        return graph_copy, sorted_vertices

    @staticmethod
    def topological_sort(graph):
        """Perform a topological sort of vertices in the graph."""
        indegree_map = {node: 0 for node in graph.vertices}
        for edge in graph.edges:
            indegree_map[edge.target] += 1

        # Use a queue to process vertices with in-degree of 0.
        zero_indegree_queue = deque(
            node for node, indegree in indegree_map.items() if indegree == 0
        )
        sorted_vertices = []

        while zero_indegree_queue:
            node = zero_indegree_queue.popleft()
            sorted_vertices.append(node)

            # Decrement the in-degrees of the neighboring vertices.
            for edge in node.edges:
                if edge.source == node:
                    indegree_map[edge.target] -= 1

                    # If a neighboring node's in-degree drops to 0, add it to the queue.
                    if indegree_map[edge.target] == 0:
                        zero_indegree_queue.append(edge.target)

        # If not all vertices are in sorted_vertices, the graph has at least one cycle.
        if len(sorted_vertices) != len(graph.vertices):
            raise ValueError(
                "The graph has at least one cycle and cannot be sorted topologically."
            )

        return sorted_vertices
