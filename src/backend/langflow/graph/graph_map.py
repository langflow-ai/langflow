from typing import Any, List, Union
from langflow.graph.graph import Graph
from langflow.graph.nodes import ConnectorNode
from langflow.graph.base import Node
from langchain.chains.base import Chain
from langflow.interface.run import get_result_and_steps


class GraphMap:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.elements = self._build_elements()
        self.intermediate_steps = []

    async def process(self, input: Any) -> Any:
        result = input
        for element in self.elements:
            # Build the graph or connector node and get the root node
            built_object = element.build()
            # check if it is a
            if isinstance(built_object, Chain):
                # result must be a str
                result = str(result)
                result, steps = await get_result_and_steps(built_object, result)
                self.intermediate_steps.append(steps)
            else:
                result = built_object(result)
        return result, self.intermediate_steps

    def _build_elements(self) -> List[Union[Node, "ConnectorNode"]]:
        elements = []
        if not self.graph.has_connectors:
            elements.append(self.graph)
            return elements

        # Create a list of connectors and their neighbors
        connectors_and_neighbors = []

        # Iterate over all nodes
        for node in self.graph.nodes:
            # Check if the current node is a ConnectorNode
            if isinstance(node, ConnectorNode):
                # Get all the neighboring nodes of the connector
                neighbors = self.graph.get_node_neighbors(node)

                # Add the connector and its neighbors to the list
                connectors_and_neighbors.append((node, neighbors))

        # For each connector and its neighbors
        for connector, neighbors in connectors_and_neighbors:
            # For each edge of the connector
            for edge in connector.edges:
                # If the edge's source is the connector, it means the edge is outgoing from the connector to a graph
                if edge.source == connector:
                    # So, add the target of the edge (which is a graph) to the elements list
                    elements.append(edge.target)

                # If the edge's target is the connector, it means the edge is incoming from a graph to the connector
                elif edge.target == connector:
                    # So, add the source of the edge (which is a graph) to the elements list
                    elements.append(edge.source)

            # Add the connector to the elements list
            elements.append(connector)
        return elements
