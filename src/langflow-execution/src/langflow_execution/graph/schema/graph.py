from enum import Enum
from pydantic import BaseModel

from loguru import logger


########################## 
# Backend representation of the graph
########################## 

class Node(BaseModel):
    id: str
    data: dict
    type: str
    parent_node_id: str | None = None
    frozen: bool | None = None

class SourceNode(BaseModel):
    base_classes: list[str]
    data_type: str
    id: str
    name: str | None
    output_types: list[str]

class TargetNode(BaseModel):
    field_name: str
    id: str
    input_types: list[str] | None
    type: str

class Edge(BaseModel):
    source: str
    target: str
    source_node: SourceNode
    target_node: TargetNode

class ExecutableGraph(BaseModel):
    """
    ExecutableGraph is a collection of nodes and edges.
    Contains the backend representation of the graph.
    """
    nodes: list[Node]
    edges: list[Edge]
    initial_nodes: list[str]


########################## 
# Frontend representation of the graph
########################## 

class Position(BaseModel):
    x: float
    y: float

class StepTypeEnum(str, Enum):
    NOTE_NODE = "noteNode"
    GENERIC_NODE = "genericNode"

class Step(BaseModel):
    id: str
    data: dict
    dragging: bool
    height: int
    width: int
    position: Position
    position_absolute: Position
    selected: bool
    parent_step_id: str
    type: StepTypeEnum

class SourceStep(BaseModel):
    base_classes: list[str]
    data_type: str
    id: str
    name: str | None
    output_types: list[str]

class TargetStep(BaseModel):
    field_name: str
    id: str
    input_types: list[str] | None
    type: str

class Connection(BaseModel):
    source: str
    target: str
    source_step: SourceStep
    target_step: TargetStep

class Graph(BaseModel):
    """
    Graph is a collection of steps and connections.
    Contains the frontend representation of the graph.
    """
    steps: list[Step]
    connections: list[Connection]

    @classmethod
    def from_payload(cls, payload: dict) -> "Graph":
        """Creates a graph from a payload.

        Args:
            payload: The payload to create the graph from.

        Returns:
            Graph: The created graph.
        """
        if "data" in payload:
            payload = payload["data"]
        
        steps = [Step(**step) for step in payload["nodes"]]
        connections = [Connection(**connection) for connection in payload["edges"]]
        try:
            return cls(steps=steps, connections=connections)
        except KeyError as exc:
            missing = [k for k in ["nodes", "edges"] if k not in payload]
            raise ValueError(f"Missing required keys: {missing}") from exc


    def to_executable_graph(self) -> ExecutableGraph:
        """Converts the graph to an executable graph.
        
        Returns:
            ExecutableGraph: The executable graph.
        """
        return ExecutableGraph(nodes=self.steps, edges=self.connections, initial_nodes=self.initial_nodes)

