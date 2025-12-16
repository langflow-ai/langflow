"""Agent graph builder - creates a complete agent graph from building blocks.

This module provides functions to programmatically build agent graphs using
the agent building block components (WhileLoop, AgentStep, ExecuteTool).

The graph structure:
    WhileLoop (start) → AgentStep → [ai_message] → (end)
                              ↓ [tool_calls]
                        ExecuteTool
                              ↓ (loop back to WhileLoop)

This is separated from the component for:
1. Easier testing of graph construction
2. Reusability in different contexts
3. Clear separation of concerns
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lfx.components.agent_blocks.agent_step import AgentStepComponent
from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.graph.graph.base import Graph

if TYPE_CHECKING:
    from lfx.events.event_manager import EventManager
    from lfx.schema.dataframe import DataFrame
    from lfx.schema.message import Message


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


def build_agent_graph(
    *,
    # Agent configuration
    model: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.1,
    tools: list[Any] | None = None,
    system_message: str = "",
    include_think_tool: bool = False,
    # Loop configuration
    max_iterations: int = 10,
    # Input configuration
    input_value: Message | str | None = None,
    initial_state: DataFrame | None = None,
    # Execution context
    execution_context: GraphExecutionContext | None = None,
    # Internal configuration
    component_id_prefix: str = "agent",
) -> Graph:
    """Build a complete agent graph ready for execution.

    Creates a fully configured agent graph with all components connected:
    - WhileLoop: Manages state accumulation across iterations
    - AgentStep: Calls the LLM and routes based on tool calls
    - ExecuteTool: Executes tool calls and returns results

    The graph structure:
        WhileLoop (start) → AgentStep → [ai_message] → (end)
                                  ↓ [tool_calls]
                            ExecuteTool
                                  ↓ (loop back)

    Note: This graph does NOT include ChatInput/ChatOutput to avoid sending
    duplicate UI events. The parent component (AgentLoopComponent) handles
    the input/output messaging.

    Args:
        model: The language model to use (e.g., "gpt-4o-mini")
        api_key: API key for the model provider
        temperature: Temperature for LLM responses (0.0-1.0)
        tools: List of tools available to the agent
        system_message: System message to guide agent behavior
        include_think_tool: Whether to add a 'think' tool for step-by-step reasoning
        max_iterations: Maximum loop iterations to prevent infinite loops
        input_value: The user's input (Message or string) for the agent
        initial_state: Optional initial state (conversation history as DataFrame)
        execution_context: Context for graph execution (flow_id, user_id, event_manager, etc.)
        component_id_prefix: Prefix for component IDs

    Returns:
        Graph ready to execute with graph.async_start()

    Example:
        ```python
        from lfx.base.agents.agent_graph import build_agent_graph, GraphExecutionContext

        # From within a component:
        context = GraphExecutionContext.from_component(self)

        graph = build_agent_graph(
            model="gpt-4o-mini",
            tools=[my_tool],
            system_message="You are a helpful assistant.",
            input_value="Hello!",
            execution_context=context,
        )

        async for result in graph.async_start(
            max_iterations=30,
            event_manager=context.event_manager,
        ):
            print(result)
        ```
    """
    # Create components
    while_loop = WhileLoopComponent(_id=f"{component_id_prefix}_while_loop")
    agent_step = AgentStepComponent(_id=f"{component_id_prefix}_agent_step")
    execute_tool = ExecuteToolComponent(_id=f"{component_id_prefix}_execute_tool")

    # Configure WhileLoop
    while_loop_config = {
        "max_iterations": max_iterations,
        "loop": execute_tool.execute_tools,
    }
    if input_value is not None:
        while_loop_config["input_value"] = input_value
    if initial_state is not None:
        while_loop_config["initial_state"] = initial_state
    while_loop.set(**while_loop_config)

    # Configure AgentStep
    agent_step_config = {
        "system_message": system_message,
        "temperature": temperature,
        "include_think_tool": include_think_tool,
        "messages": while_loop.loop_output,
    }
    if model:
        agent_step_config["model"] = model
    if api_key:
        agent_step_config["api_key"] = api_key
    if tools:
        agent_step_config["tools"] = tools
    agent_step.set(**agent_step_config)

    # Configure ExecuteTool
    execute_tool_config = {"ai_message": agent_step.get_tool_calls}
    if tools:
        execute_tool_config["tools"] = tools
    execute_tool.set(**execute_tool_config)

    # Extract context values for Graph construction
    flow_id = None
    flow_name = None
    user_id = None
    context = None

    if execution_context is not None:
        flow_id = execution_context.flow_id
        flow_name = f"{execution_context.flow_name}_agent_loop" if execution_context.flow_name else "agent_loop"
        user_id = execution_context.user_id
        context = execution_context.context

    # Create graph from WhileLoop (start) to AgentStep's ai_message (end)
    graph = Graph(
        start=while_loop,
        end=agent_step,
        flow_id=flow_id,
        flow_name=flow_name,
        user_id=user_id,
        context=context,
    )

    # Set session_id if available
    if execution_context is not None and execution_context.session_id:
        graph.session_id = execution_context.session_id

    return graph
