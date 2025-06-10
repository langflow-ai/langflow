from abc import ABC, abstractmethod
from typing import Any

from langflow_execution.graph.api.schema import GraphExecutionRequest, GraphExecutionResponse

class GraphExecutionInterface(ABC):
    """Interface for graph execution implementations."""
    
    @abstractmethod
    def run(self, input: GraphExecutionRequest) -> GraphExecutionResponse:
        """
        Execute the graph with given inputs.
        
        Args:
            inputs: Dictionary of input values for the graph execution
            
        Returns:
            Dictionary containing the execution results
        """
        
