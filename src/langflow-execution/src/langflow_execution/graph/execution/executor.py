import copy
from typing import Any
from langflow.graph.graph.utils import add_parent_node_id
from loguru import logger

from langflow_execution.graph.schema.graph import Graph, Node, Edge

class GraphExecutor:
    def __init__(self, graph: Graph):
        """Initialize the graph executor with a Graph instance.
        
        Args:
            graph: The Graph instance to execute
        """
        self.graph = graph
        self._step_map: dict[str, Node] = {step.id: step for step in graph.steps}
        self._edge_map: dict[str, list[Edge]] = self._build_edge_map()
        self.initial_steps = []
        self._add_steps_and_edges(self.graph.steps, self.graph.edges)
        self._build_graph()


    def _build_edge_map(self) -> dict[str, list[Edge]]:
        """Build a map of step IDs to their outgoing edges."""
        edge_map = {}
        for edge in self.graph.edges:
            source_id = edge.source
            if source_id not in edge_map:
                edge_map[source_id] = []
            edge_map[source_id].append(edge)
        return edge_map

    def _add_steps_and_edges(self, steps: list[Node], edges: list[Edge]) -> None:
        """Add steps and edges to the graph."""
        for step in steps:
            if step.id: # TODO: FRAZ - are only id'd steps the initial steps?
                self.initial_steps.append(step.id)

        # TODO: Handle ungrouping

    def _build_graph(self) -> None:
        """Build the graph from the steps and edges."""
        vertices = self._build_vertices()
        # TODO: FRAZ NEXT




    async def execute(self, inputs: dict[str, Any] = None) -> dict[str, Any]:
        """Execute the graph starting from input steps.
        
        Args:
            inputs: Optional input values for the graph execution
            
        Returns:
            Dict containing the execution results
        """
        if inputs is None:
            inputs = {}
            
        # TODO: Implement actual execution logic
        # This will involve:
        # 1. Finding input steps
        # 2. Executing steps in topological order
        # 3. Handling edge conditions
        # 4. Managing state between steps
        
        return {}
