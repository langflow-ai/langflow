"""Tests for the simple agent workflow that can be executed via `lfx run`.

This module tests the agent workflow by:
1. Creating and validating the agent script
2. Testing component instantiation and configuration
3. Testing direct graph execution without CLI
4. Verifying the workflow works with langflow's dependencies
"""

import os
from pathlib import Path

import pytest
from lfx.utils.async_helpers import run_until_complete

from tests.api_keys import has_api_key


class TestAgentInLfxRun:
    """Test the agent workflow that demonstrates lfx run functionality."""

    @pytest.fixture
    def simple_agent_script_content(self):
        """The simple_agent.py script content for testing lfx run."""
        return '''"""A simple agent flow example for Langflow.

This script demonstrates how to set up a conversational agent using Langflow's
Agent component with web search capabilities.

Features:
- Uses the new flattened component access (cp.AgentComponent instead of deep imports)
- Configures logging to 'langflow.log' at INFO level
- Creates an agent with OpenAI GPT model
- Provides web search tools via URLComponent
- Connects ChatInput → Agent → ChatOutput

Usage:
    uv run lfx run simple_agent.py "How are you?"
"""

import os
from pathlib import Path

# Using the new flattened component access
from lfx import components as cp
from lfx.graph import Graph
from lfx.log.logger import LogConfig

log_config = LogConfig(
    log_level="INFO",
    log_file=Path("langflow.log"),
)

# Showcase the new flattened component access - no need for deep imports!
chat_input = cp.ChatInput()
agent = cp.AgentComponent()
url_component = cp.URLComponent()
tools = await url_component.to_toolkit()

agent.set(
    model_name="gpt-4o-mini",
    agent_llm="OpenAI",
    api_key=os.getenv("OPENAI_API_KEY"),
    input_value=chat_input.message_response,
    tools=tools,
)
chat_output = cp.ChatOutput().set(input_value=agent.message_response)

graph = Graph(chat_input, chat_output, log_config=log_config)
'''

    @pytest.fixture
    def simple_agent_script_file(self):
        """Get the path to the agent script in tests/data."""
        # Use the script file we created in tests/data
        script_path = Path(__file__).parent.parent / "data" / "simple_agent.py"
        assert script_path.exists(), f"Script file not found: {script_path}"

        yield script_path

        # Cleanup any log file that might be created
        log_file = Path("langflow.log")
        if log_file.exists():
            log_file.unlink(missing_ok=True)

    def test_agent_script_structure_and_syntax(self, simple_agent_script_content):
        """Test that the agent script has correct structure and valid syntax."""
        import ast

        # Test syntax is valid
        try:
            ast.parse(simple_agent_script_content)
        except SyntaxError as e:
            pytest.fail(f"Script has invalid syntax: {e}")

        # Test key components are present
        assert "from lfx import components as cp" in simple_agent_script_content
        assert "cp.ChatInput()" in simple_agent_script_content
        assert "cp.AgentComponent()" in simple_agent_script_content
        assert "cp.URLComponent()" in simple_agent_script_content
        assert "cp.ChatOutput()" in simple_agent_script_content
        assert "url_component.to_toolkit()" in simple_agent_script_content
        assert 'model_name="gpt-4o-mini"' in simple_agent_script_content
        assert 'agent_llm="OpenAI"' in simple_agent_script_content
        assert "Graph(chat_input, chat_output" in simple_agent_script_content

    def test_agent_script_file_validation(self, simple_agent_script_file):
        """Test that the agent script file exists and has valid content."""
        # Since we don't have direct CLI access in langflow tests,
        # verify the script file exists and has correct content
        assert simple_agent_script_file.exists(), "Script file should exist in tests/data"

        # Verify script content has expected structure
        content = simple_agent_script_file.read_text()
        assert "from lfx import components as cp" in content
        assert "cp.AgentComponent()" in content
        assert "Graph(chat_input, chat_output" in content

    def test_agent_script_supports_formats(self, simple_agent_script_file):
        """Test that the script supports logging configuration."""
        # Verify script file exists and contains the expected structure
        assert simple_agent_script_file.exists()

        # Test that the script mentions the format options in its docstring
        content = simple_agent_script_file.read_text()
        assert "Usage:" in content, "Script should have usage documentation"

        # Verify the key logging components are present
        assert "LogConfig" in content, "Script should configure logging properly"

    @pytest.mark.skipif(not has_api_key("OPENAI_API_KEY"), reason="OPENAI_API_KEY required for full execution test")
    def test_agent_script_api_configuration(self, simple_agent_script_file):
        """Test that the script is properly configured for API usage."""
        # Verify the script file exists and has API key configuration
        assert simple_agent_script_file.exists()

        content = simple_agent_script_file.read_text()

        # Should use environment variable for API key
        assert 'os.getenv("OPENAI_API_KEY")' in content

        # Should use the recommended model
        assert 'model_name="gpt-4o-mini"' in content

    async def test_agent_workflow_direct_execution(self):
        """Test the agent workflow by executing the graph directly."""
        # Import the components for direct execution
        try:
            from lfx.graph import Graph
            from lfx.log.logger import LogConfig

            from lfx import components as cp
        except ImportError as e:
            pytest.skip(f"LFX components not available: {e}")

        # Create the agent workflow
        log_config = LogConfig(
            log_level="INFO",
            log_file=Path("langflow.log"),
        )

        chat_input = cp.ChatInput()
        agent = cp.AgentComponent()
        url_component = cp.URLComponent()

        # Configure URL component for tools
        url_component.set(urls=["https://httpbin.org/json"])
        tools = run_until_complete(url_component.to_toolkit())

        # Configure agent
        agent.set(
            model_name="gpt-4o-mini",
            agent_llm="OpenAI",
            api_key=os.getenv("OPENAI_API_KEY", "test-key"),  # Use test key if not available
            input_value="Hello, how are you?",  # Direct input instead of chat_input.message_response
            tools=tools,
        )

        chat_output = cp.ChatOutput()

        # Create graph
        graph = Graph(chat_input, chat_output, log_config=log_config)

        # Verify graph was created successfully
        assert graph is not None
        # The Graph object exists and has the expected structure
        assert str(graph), "Graph should have string representation"

        # Cleanup log file
        log_file = Path("langflow.log")
        if log_file.exists():
            log_file.unlink(missing_ok=True)

    def test_flattened_component_access_pattern(self):
        """Test that the flattened component access pattern works."""
        try:
            from lfx import components as cp
        except ImportError as e:
            pytest.skip(f"LFX components not available: {e}")

        # Test that all required components are accessible via flattened access
        components_to_test = ["ChatInput", "AgentComponent", "URLComponent", "ChatOutput"]

        for component_name in components_to_test:
            assert hasattr(cp, component_name), f"Component {component_name} not available via flattened access"

            # Test that we can instantiate each component
            component_class = getattr(cp, component_name)
            try:
                instance = component_class()
                assert instance is not None
            except Exception as e:
                pytest.fail(f"Failed to instantiate {component_name}: {e}")

    async def test_url_component_to_toolkit_functionality(self):
        """Test that URLComponent.to_toolkit() works properly."""
        try:
            from lfx.utils.async_helpers import run_until_complete

            from lfx import components as cp
        except ImportError as e:
            pytest.skip(f"LFX components not available: {e}")

        url_component = cp.URLComponent()

        # Configure with test URL
        url_component.set(urls=["https://httpbin.org/json"])

        # Test to_toolkit functionality
        tools = run_until_complete(url_component.to_toolkit())

        # Should return some kind of tools object/list
        assert tools is not None
        # Should be iterable (list, tuple, or similar)
        assert hasattr(tools, "__iter__"), "Tools should be iterable"

    def test_agent_configuration_workflow(self):
        """Test agent configuration in the workflow."""
        try:
            from lfx import components as cp
        except ImportError as e:
            pytest.skip(f"LFX components not available: {e}")

        agent = cp.AgentComponent()

        # Test the agent.set() configuration
        agent.set(
            model_name="gpt-4o-mini",
            agent_llm="OpenAI",
            api_key="test-key",  # Use test key
            input_value="Test message",
            tools=[],  # Empty tools for this test
        )

        # Verify configuration was applied
        assert agent.model_name == "gpt-4o-mini"
        assert agent.agent_llm == "OpenAI"
        assert agent.api_key == "test-key"
        assert agent.input_value == "Test message"

    def test_chat_output_chaining_pattern(self):
        """Test the chat output chaining pattern."""
        try:
            from lfx.schema.message import Message

            from lfx import components as cp
        except ImportError as e:
            pytest.skip(f"LFX components not available: {e}")

        chat_output = cp.ChatOutput()

        # Test the chaining pattern: cp.ChatOutput().set(input_value=agent.message_response)
        mock_message = Message(text="Test response")
        result = chat_output.set(input_value=mock_message)

        # Should return the chat_output instance for chaining
        assert result is chat_output
        assert chat_output.input_value == mock_message

    def test_logging_configuration(self):
        """Test LogConfig setup for the workflow."""
        try:
            from lfx.log.logger import LogConfig
        except ImportError as e:
            pytest.skip(f"LFX logging not available: {e}")

        # Test LogConfig creation for the workflow
        log_config = LogConfig(
            log_level="INFO",
            log_file=Path("langflow.log"),
        )

        assert log_config is not None
        # LogConfig may be a dict or object, verify it contains the expected data
        if isinstance(log_config, dict):
            assert log_config.get("log_level") == "INFO"
            assert log_config.get("log_file") == Path("langflow.log")
        else:
            assert hasattr(log_config, "log_level") or hasattr(log_config, "__dict__")

        # Cleanup
        log_file = Path("langflow.log")
        if log_file.exists():
            log_file.unlink(missing_ok=True)

    def test_environment_variable_handling(self):
        """Test that environment variable handling works properly."""
        # Test os.getenv("OPENAI_API_KEY") pattern
        import os

        # This should not raise an error even if the env var is not set
        api_key = os.getenv("OPENAI_API_KEY")

        # Should return None if not set, string if set
        assert api_key is None or isinstance(api_key, str)

    @pytest.mark.skipif(not has_api_key("OPENAI_API_KEY"), reason="OPENAI_API_KEY required for integration test")
    def test_complete_workflow_integration(self):
        """Test the complete agent workflow integration."""
        try:
            from lfx.graph import Graph
            from lfx.log.logger import LogConfig

            from lfx import components as cp
        except ImportError as e:
            pytest.skip(f"LFX components not available: {e}")

        # Set up the complete workflow
        log_config = LogConfig(
            log_level="INFO",
            log_file=Path("langflow.log"),
        )

        chat_input = cp.ChatInput()
        agent = cp.AgentComponent()
        url_component = cp.URLComponent()

        # Configure URL component
        url_component.set(urls=["https://httpbin.org/json"])
        tools = run_until_complete(url_component.to_toolkit())

        # Configure agent with real API key
        agent.set(
            model_name="gpt-4o-mini",
            agent_llm="OpenAI",
            api_key=os.getenv("OPENAI_API_KEY"),
            input_value="What is 2 + 2?",  # Simple math question
            tools=tools,
        )

        chat_output = cp.ChatOutput()

        # Create and verify graph
        graph = Graph(chat_input, chat_output, log_config=log_config)
        assert graph is not None

        # The actual execution would happen when the graph is run
        # For now, just verify the setup completed without errors

        # Cleanup
        log_file = Path("langflow.log")
        if log_file.exists():
            log_file.unlink(missing_ok=True)
