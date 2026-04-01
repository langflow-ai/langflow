"""Tests for agent utility functions."""

from unittest.mock import Mock

from lfx.base.agents.utils import get_chat_output_sender_name


class TestGetChatOutputSenderName:
    """Test suite for get_chat_output_sender_name function."""

    def test_get_chat_output_sender_name_no_graph(self):
        """Test that function returns None when component has no graph."""
        # Create a mock component without graph attribute
        component = Mock()
        del component.graph  # Remove graph attribute

        result = get_chat_output_sender_name(component)

        assert result is None

    def test_get_chat_output_sender_name_graph_none(self):
        """Test that function returns None when component.graph is None."""
        # Create a mock component with None graph
        component = Mock()
        component.graph = None

        result = get_chat_output_sender_name(component)

        assert result is None

    def test_get_chat_output_sender_name_no_vertices(self):
        """Test that function returns None when graph has no vertices."""
        # Create a mock component with empty vertices
        component = Mock()
        component.graph = Mock()
        component.graph.vertices = []

        result = get_chat_output_sender_name(component)

        assert result is None

    def test_get_chat_output_sender_name_no_chat_output(self):
        """Test that function returns None when no ChatOutput component exists."""
        # Create mock vertices that are not ChatOutput
        vertex1 = Mock()
        vertex1.data = {"type": "ChatInput"}
        vertex1.raw_params = {"sender_name": "User"}

        vertex2 = Mock()
        vertex2.data = {"type": "TextOutput"}
        vertex2.raw_params = {"value": "test"}

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [vertex1, vertex2]

        result = get_chat_output_sender_name(component)

        assert result is None

    def test_get_chat_output_sender_name_found(self):
        """Test that function returns sender_name when ChatOutput component exists."""
        # Create a mock ChatOutput vertex
        chat_output_vertex = Mock()
        chat_output_vertex.data = {"type": "ChatOutput"}
        chat_output_vertex.raw_params = {"sender_name": "Assistant"}

        # Create other vertices
        other_vertex = Mock()
        other_vertex.data = {"type": "ChatInput"}
        other_vertex.raw_params = {"value": "test"}

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [other_vertex, chat_output_vertex]

        result = get_chat_output_sender_name(component)

        assert result == "Assistant"

    def test_get_chat_output_sender_name_first_match(self):
        """Test that function returns sender_name from first ChatOutput component found."""
        # Create multiple mock ChatOutput vertices
        chat_output1 = Mock()
        chat_output1.data = {"type": "ChatOutput"}
        chat_output1.raw_params = {"sender_name": "Assistant1"}

        chat_output2 = Mock()
        chat_output2.data = {"type": "ChatOutput"}
        chat_output2.raw_params = {"sender_name": "Assistant2"}

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [chat_output1, chat_output2]

        result = get_chat_output_sender_name(component)

        # Should return the first one found
        assert result == "Assistant1"

    def test_get_chat_output_sender_name_missing_sender_name(self):
        """Test that function returns None when ChatOutput has no sender_name parameter."""
        # Create a mock ChatOutput vertex without sender_name
        chat_output_vertex = Mock()
        chat_output_vertex.data = {"type": "ChatOutput"}
        chat_output_vertex.raw_params = {"other_param": "value"}  # No sender_name

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [chat_output_vertex]

        result = get_chat_output_sender_name(component)

        assert result is None

    def test_get_chat_output_sender_name_empty_sender_name(self):
        """Test that function returns empty string when sender_name is empty."""
        # Create a mock ChatOutput vertex with empty sender_name
        chat_output_vertex = Mock()
        chat_output_vertex.data = {"type": "ChatOutput"}
        chat_output_vertex.raw_params = {"sender_name": ""}

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [chat_output_vertex]

        result = get_chat_output_sender_name(component)

        assert result == ""

    def test_get_chat_output_sender_name_none_sender_name(self):
        """Test that function returns None when sender_name is None."""
        # Create a mock ChatOutput vertex with None sender_name
        chat_output_vertex = Mock()
        chat_output_vertex.data = {"type": "ChatOutput"}
        chat_output_vertex.raw_params = {"sender_name": None}

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [chat_output_vertex]

        result = get_chat_output_sender_name(component)

        assert result is None

    def test_get_chat_output_sender_name_vertex_missing_data(self):
        """Test that function handles vertex without data attribute gracefully."""
        # Create a mock vertex without data attribute
        bad_vertex = Mock()
        del bad_vertex.data  # Remove data attribute

        # Create a good ChatOutput vertex
        good_vertex = Mock()
        good_vertex.data = {"type": "ChatOutput"}
        good_vertex.raw_params = {"sender_name": "Assistant"}

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [bad_vertex, good_vertex]

        result = get_chat_output_sender_name(component)

        # Should still find the good vertex
        assert result == "Assistant"

    def test_get_chat_output_sender_name_vertex_missing_raw_params(self):
        """Test that function handles vertex without raw_params attribute gracefully."""
        # Create a mock ChatOutput vertex without raw_params
        chat_output_vertex = Mock()
        chat_output_vertex.data = {"type": "ChatOutput"}
        del chat_output_vertex.raw_params  # Remove raw_params attribute

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [chat_output_vertex]

        result = get_chat_output_sender_name(component)

        assert result is None

    def test_get_chat_output_sender_name_case_sensitivity(self):
        """Test that function is case sensitive for component type matching."""
        # Create vertices with different case variations
        vertex1 = Mock()
        vertex1.data = {"type": "chatoutput"}  # lowercase
        vertex1.raw_params = {"sender_name": "Assistant1"}

        vertex2 = Mock()
        vertex2.data = {"type": "CHATOUTPUT"}  # uppercase
        vertex2.raw_params = {"sender_name": "Assistant2"}

        vertex3 = Mock()
        vertex3.data = {"type": "ChatOutput"}  # correct case
        vertex3.raw_params = {"sender_name": "Assistant3"}

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [vertex1, vertex2, vertex3]

        result = get_chat_output_sender_name(component)

        # Should only match exact case "ChatOutput"
        assert result == "Assistant3"

    def test_get_chat_output_sender_name_complex_graph(self):
        """Test function with a complex graph containing multiple component types."""
        # Create various component types
        chat_input = Mock()
        chat_input.data = {"type": "ChatInput"}
        chat_input.raw_params = {"value": "Hello"}

        text_output = Mock()
        text_output.data = {"type": "TextOutput"}
        text_output.raw_params = {"value": "World"}

        agent = Mock()
        agent.data = {"type": "Agent"}
        agent.raw_params = {"system_prompt": "You are helpful"}

        chat_output = Mock()
        chat_output.data = {"type": "ChatOutput"}
        chat_output.raw_params = {"sender_name": "AI Assistant", "should_store_message": True}

        llm = Mock()
        llm.data = {"type": "OpenAI"}
        llm.raw_params = {"model_name": "gpt-4"}

        component = Mock()
        component.graph = Mock()
        component.graph.vertices = [chat_input, text_output, agent, chat_output, llm]

        result = get_chat_output_sender_name(component)

        assert result == "AI Assistant"

    def test_get_chat_output_sender_name_integration_with_agent(self):
        """Test integration with agent component showing how it would be used."""
        # Create a mock agent component
        agent_component = Mock()

        # Create a mock graph with ChatOutput
        chat_output_vertex = Mock()
        chat_output_vertex.data = {"type": "ChatOutput"}
        chat_output_vertex.raw_params = {"sender_name": "My Custom Agent", "should_store_message": True, "sender": "AI"}

        agent_component.graph = Mock()
        agent_component.graph.vertices = [chat_output_vertex]

        # Test the function as it would be used in the agent
        result = get_chat_output_sender_name(agent_component)

        # This simulates the usage in agent.py:
        # sender_name = get_chat_output_sender_name(self) or self.display_name or "Agent"
        agent_component.display_name = "Default Agent Name"
        final_sender_name = result or agent_component.display_name or "Agent"

        assert result == "My Custom Agent"
        assert final_sender_name == "My Custom Agent"

    def test_get_chat_output_sender_name_integration_fallback(self):
        """Test integration showing fallback behavior when no ChatOutput found."""
        # Create a mock agent component without ChatOutput
        agent_component = Mock()
        agent_component.display_name = "My Agent"

        # Create a mock graph without ChatOutput
        other_vertex = Mock()
        other_vertex.data = {"type": "ChatInput"}
        other_vertex.raw_params = {"value": "Hello"}

        agent_component.graph = Mock()
        agent_component.graph.vertices = [other_vertex]

        # Test the function
        result = get_chat_output_sender_name(agent_component)

        # Simulate the fallback logic used in agent.py
        final_sender_name = result or agent_component.display_name or "Agent"

        assert result is None
        assert final_sender_name == "My Agent"
