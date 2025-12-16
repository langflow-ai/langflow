"""Tests for the agent graph builder module.

These tests verify that build_agent_graph correctly constructs agent graphs
with proper structure and configuration.
"""

from lfx.base.agents.agent_graph import GraphExecutionContext, build_agent_graph
from lfx.components.agent_blocks.agent_step import AgentStepComponent
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.graph.graph.base import Graph


class MockTool:
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"

    async def ainvoke(self, args: dict) -> str:
        return f"Mock result for {args}"


class TestBuildAgentGraph:
    """Tests for build_agent_graph function."""

    def test_returns_graph(self):
        """Test that build_agent_graph returns a Graph."""
        graph = build_agent_graph()
        assert isinstance(graph, Graph)

    def test_graph_is_cyclic(self):
        """Test that the built graph is cyclic (has a loop)."""
        tools = [MockTool()]
        graph = build_agent_graph(tools=tools)
        graph.prepare()
        assert graph.is_cyclic is True

    def test_graph_starts_with_while_loop(self):
        """Test that the graph starts with WhileLoop."""
        graph = build_agent_graph()
        assert isinstance(graph._start, WhileLoopComponent)

    def test_graph_ends_with_agent_step(self):
        """Test that the graph ends with AgentStep."""
        graph = build_agent_graph()
        assert isinstance(graph._end, AgentStepComponent)

    def test_custom_component_id_prefix(self):
        """Test that custom ID prefix is used for components."""
        graph = build_agent_graph(component_id_prefix="my_agent")
        assert "my_agent" in graph._start._id
        assert "my_agent" in graph._end._id

    def test_input_value_set_on_while_loop(self):
        """Test that input_value is set on WhileLoop."""
        graph = build_agent_graph(input_value="Hello!")
        assert graph._start.input_value == "Hello!"

    def test_system_message_passed_to_graph(self):
        """Test that system_message is set when building graph."""
        # We can't easily inspect internal components, but we can verify
        # the graph builds without error with a system message
        graph = build_agent_graph(system_message="You are a test assistant.")
        assert isinstance(graph, Graph)

    def test_tools_passed_to_graph(self):
        """Test that tools are passed when building graph."""
        tools = [MockTool()]
        graph = build_agent_graph(tools=tools)
        assert isinstance(graph, Graph)
        # Graph should be cyclic when tools are present
        graph.prepare()
        assert graph.is_cyclic is True


class TestGraphExecutionContext:
    """Tests for GraphExecutionContext dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        ctx = GraphExecutionContext()
        assert ctx.flow_id is None
        assert ctx.flow_name is None
        assert ctx.user_id is None
        assert ctx.session_id is None
        assert ctx.context == {}
        assert ctx.event_manager is None

    def test_from_component_with_graph(self):
        """Test creating context from a component with graph attributes."""

        class MockGraph:
            flow_id = "test-flow-id"
            flow_name = "Test Flow"
            session_id = "test-session"
            context = {"key": "value"}

        class MockComponent:
            graph = MockGraph()
            user_id = "test-user"
            _event_manager = None

        ctx = GraphExecutionContext.from_component(MockComponent())
        assert ctx.flow_id == "test-flow-id"
        assert ctx.flow_name == "Test Flow"
        assert ctx.session_id == "test-session"
        assert ctx.user_id == "test-user"
        assert ctx.context == {"key": "value"}

    def test_from_component_without_graph(self):
        """Test creating context from a component without graph."""

        class MockComponent:
            graph = None
            user_id = "test-user"

        ctx = GraphExecutionContext.from_component(MockComponent())
        assert ctx.flow_id is None
        assert ctx.user_id == "test-user"


class TestBuildAgentGraphWithContext:
    """Tests for build_agent_graph with execution context."""

    def test_context_sets_graph_flow_id(self):
        """Test that execution context sets flow_id on graph."""
        ctx = GraphExecutionContext(flow_id="my-flow-id")
        graph = build_agent_graph(execution_context=ctx)
        assert graph.flow_id == "my-flow-id"

    def test_context_sets_graph_user_id(self):
        """Test that execution context sets user_id on graph."""
        ctx = GraphExecutionContext(user_id="my-user-id")
        graph = build_agent_graph(execution_context=ctx)
        assert graph.user_id == "my-user-id"

    def test_context_sets_graph_session_id(self):
        """Test that execution context sets session_id on graph."""
        ctx = GraphExecutionContext(session_id="my-session-id")
        graph = build_agent_graph(execution_context=ctx)
        assert graph.session_id == "my-session-id"

    def test_context_sets_graph_flow_name(self):
        """Test that execution context sets flow_name on graph."""
        ctx = GraphExecutionContext(flow_name="My Flow")
        graph = build_agent_graph(execution_context=ctx)
        assert graph.flow_name == "My Flow_agent_loop"


class TestAgentGraphIntegration:
    """Integration tests for the agent graph."""

    def test_graph_has_three_vertices(self):
        """Test that the graph has three vertices: WhileLoop, AgentStep, ExecuteTool."""
        tools = [MockTool()]
        graph = build_agent_graph(tools=tools)
        graph.prepare()

        # Should have 3 vertices
        assert len(graph.vertices) == 3

    def test_graph_structure_with_tools(self):
        """Test the complete graph structure with tools."""
        tools = [MockTool()]
        graph = build_agent_graph(
            tools=tools,
            system_message="You are a helpful assistant.",
            component_id_prefix="test",
        )
        graph.prepare()

        # Verify vertex IDs
        vertex_ids = {v.id for v in graph.vertices}
        assert "test_while_loop" in vertex_ids
        assert "test_agent_step" in vertex_ids
        assert "test_execute_tool" in vertex_ids
