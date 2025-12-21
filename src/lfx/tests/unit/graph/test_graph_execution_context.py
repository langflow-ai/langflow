"""Tests for GraphExecutionContext.

These tests verify that GraphExecutionContext correctly extracts
context from components for use in subgraph execution.
"""

from lfx.graph import GraphExecutionContext


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
        assert ctx.stream_to_playground is False

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

    def test_from_component_with_event_manager_method(self):
        """Test that get_event_manager method is used if available."""

        class MockEventManager:
            pass

        class MockComponent:
            graph = None

            def get_event_manager(self):
                return MockEventManager()

        ctx = GraphExecutionContext.from_component(MockComponent())
        assert isinstance(ctx.event_manager, MockEventManager)

    def test_from_component_with_stream_to_playground(self):
        """Test that is_connected_to_chat_output is checked."""

        class MockComponent:
            graph = None

            def is_connected_to_chat_output(self):
                return True

        ctx = GraphExecutionContext.from_component(MockComponent())
        assert ctx.stream_to_playground is True

    def test_context_is_copied(self):
        """Test that context dict is copied, not referenced."""

        class MockGraph:
            flow_id = None
            flow_name = None
            session_id = None
            context = {"original": "value"}

        class MockComponent:
            graph = MockGraph()

        ctx = GraphExecutionContext.from_component(MockComponent())
        ctx.context["new"] = "added"

        # Original should be unchanged
        assert "new" not in MockGraph.context
