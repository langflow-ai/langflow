from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

from typing_extensions import NotRequired, TypedDict

from lfx.graph.edge.schema import EdgeData
from lfx.graph.vertex.schema import NodeData

if TYPE_CHECKING:
    from lfx.events.event_manager import EventManager
    from lfx.graph.schema import ResultData
    from lfx.graph.vertex.base import Vertex
    from lfx.schema.log import LoggableType


class ViewPort(TypedDict):
    x: float
    y: float
    zoom: float


class GraphData(TypedDict):
    nodes: list[NodeData]
    edges: list[EdgeData]
    viewport: NotRequired[ViewPort]


class GraphDump(TypedDict, total=False):
    data: GraphData
    is_component: bool
    name: str
    description: str
    endpoint_name: str


class VertexBuildResult(NamedTuple):
    result_dict: ResultData
    params: str
    valid: bool
    artifacts: dict
    vertex: Vertex


class OutputConfigDict(TypedDict):
    cache: bool


class StartConfigDict(TypedDict):
    output: OutputConfigDict


class LogCallbackFunction(Protocol):
    def __call__(self, event_name: str, log: LoggableType) -> None: ...


@dataclass
class GraphExecutionContext:
    """Context data required for executing a graph or subgraph.

    This dataclass encapsulates all the context information that needs to be
    passed when building and executing a graph inside a component. It provides
    a clean interface for passing context from a parent component to an internal
    graph, ensuring proper event propagation, tracing, and session management.

    Attributes:
        flow_id: Unique identifier for the flow
        flow_name: Human-readable name of the flow
        user_id: Identifier of the user executing the flow
        session_id: Identifier for the current session
        context: Additional contextual information (e.g., variables, settings)
        event_manager: Event manager for propagating UI events from subgraph execution
        stream_to_playground: Whether inner graph components should stream to playground.
            This is True when the parent component is connected to ChatOutput.
    """

    flow_id: str | None = None
    flow_name: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    event_manager: EventManager | None = None
    stream_to_playground: bool = False

    @classmethod
    def from_component(cls, component) -> GraphExecutionContext:
        """Create a GraphExecutionContext from a component's attributes.

        This factory method extracts all relevant context from a component
        that has access to a graph (either a real Graph or a PlaceholderGraph).

        Args:
            component: A Component instance with graph context

        Returns:
            GraphExecutionContext populated with the component's context
        """
        flow_id = None
        flow_name = None
        user_id = None
        session_id = None
        context = {}
        event_manager = None

        # Get values from the component's graph if available
        if hasattr(component, "graph") and component.graph is not None:
            graph = component.graph
            flow_id = graph.flow_id if hasattr(graph, "flow_id") else None
            flow_name = graph.flow_name if hasattr(graph, "flow_name") else None
            session_id = graph.session_id if hasattr(graph, "session_id") else None
            context = dict(graph.context) if hasattr(graph, "context") and graph.context else {}

        # user_id is often directly on the component
        if hasattr(component, "user_id"):
            user_id = component.user_id

        # event_manager is typically on the component
        if hasattr(component, "get_event_manager"):
            event_manager = component.get_event_manager()
        elif hasattr(component, "_event_manager"):
            event_manager = component._event_manager  # noqa: SLF001

        # Check if the parent component is connected to ChatOutput
        # If so, inner graph components should stream to playground
        stream_to_playground = False
        if hasattr(component, "is_connected_to_chat_output"):
            stream_to_playground = component.is_connected_to_chat_output()

        return cls(
            flow_id=flow_id,
            flow_name=flow_name,
            user_id=user_id,
            session_id=session_id,
            context=context,
            event_manager=event_manager,
            stream_to_playground=stream_to_playground,
        )
