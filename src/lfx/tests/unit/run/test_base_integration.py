"""Integration tests for run.base module with minimal mocking.

This file demonstrates how to test run_flow with real components and graphs,
reducing the need for extensive mocking while still maintaining test isolation.
"""

from pathlib import Path

import pytest
from lfx.run.base import RunError, run_flow


class TestRunFlowIntegrationMinimalMocking:
    """Integration tests that use real components with minimal mocking."""

    @pytest.fixture
    def simple_python_graph(self, tmp_path):
        """Create a simple Python graph script that can actually run."""
        script_content = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph

# Create a simple pass-through graph
chat_input = ChatInput()
chat_output = ChatOutput().set(input_value=chat_input.message_response)

graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "simple_graph.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.fixture
    def env_consuming_graph(self, tmp_path):
        """Create a graph that reads from environment variables."""
        script_content = '''
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output, Input
from lfx.schema.message import Message
from lfx.graph import Graph

class EnvironmentReader(Component):
    """A simple component that reads environment variables."""
    inputs = [Input(name="trigger", input_types=["Message"], field_type="Message")]
    outputs = [Output(name="result", method="read_env", types=["Message"])]

    def read_env(self) -> Message:
        # Read from graph context (where env vars are injected)
        env_vars = self.graph.context.get("request_variables", {})
        api_key = env_vars.get("API_KEY", "no-key")
        return Message(text=f"API_KEY={api_key}")

chat_input = ChatInput()
env_reader = EnvironmentReader()
env_reader.set(trigger=chat_input.message_response)
chat_output = ChatOutput().set(input_value=env_reader.read_env)

graph = Graph(chat_input, chat_output)
'''
        script_path = tmp_path / "env_graph.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.mark.asyncio
    async def test_run_flow_with_real_graph_no_env_vars(self, simple_python_graph):
        """Test run_flow with a real graph, no environment variables."""
        result = await run_flow(
            script_path=simple_python_graph,
            input_value="Hello World",
            global_variables=None,
            verbose=False,
            check_variables=False,  # Skip validation for speed
            timing=False,
        )

        assert result["success"] is True
        assert "Hello World" in result["result"]

    @pytest.mark.asyncio
    async def test_run_flow_with_env_vars_real_graph(self, env_consuming_graph):
        """Test run_flow with environment variables using a real graph."""
        env_vars = {"API_KEY": "test-key-12345"}

        result = await run_flow(
            script_path=env_consuming_graph,
            input_value="test",
            global_variables=env_vars,
            verbose=False,
            check_variables=False,
            timing=False,
        )

        assert result["success"] is True
        assert "API_KEY=test-key-12345" in result["result"]

    @pytest.mark.asyncio
    async def test_run_flow_without_env_vars_shows_default(self, env_consuming_graph):
        """Test that missing env vars show default values."""
        result = await run_flow(
            script_path=env_consuming_graph,
            input_value="test",
            global_variables=None,  # No env vars provided
            verbose=False,
            check_variables=False,
            timing=False,
        )

        assert result["success"] is True
        assert "API_KEY=no-key" in result["result"]

    @pytest.mark.asyncio
    async def test_run_flow_json_inline_input(self):
        """Test run_flow with inline JSON (minimal external dependencies)."""
        # Create a simple JSON structure that represents a basic flow
        # Note: This would need to match the actual JSON format expected by the system

        # For now, we'll test the JSON processing part with inline JSON
        # that will be converted to a temp file
        simple_json = '{"test": "data"}'  # This will fail at graph loading, but tests JSON processing

        with pytest.raises(RunError):  # Will fail when trying to load the graph
            await run_flow(flow_json=simple_json, verbose=False, check_variables=False)

    @pytest.mark.asyncio
    async def test_run_flow_stdin_input(self):
        """Test run_flow with stdin input."""
        import sys
        from io import StringIO

        # Create mock stdin content
        stdin_content = '{"test": "stdin_data"}'

        # Mock stdin
        old_stdin = sys.stdin
        sys.stdin = StringIO(stdin_content)

        try:
            with pytest.raises(RunError):  # Will fail at graph loading
                await run_flow(stdin=True, verbose=False, check_variables=False)
        finally:
            sys.stdin = old_stdin


class TestRunFlowErrorHandlingIntegration:
    """Integration tests for error handling with real components."""

    @pytest.mark.asyncio
    async def test_run_flow_invalid_script_path(self):
        """Test error handling with non-existent script."""
        nonexistent = Path("/definitely/does/not/exist.py")

        with pytest.raises(RunError):
            await run_flow(script_path=nonexistent)

    @pytest.mark.asyncio
    async def test_run_flow_invalid_file_extension(self, tmp_path):
        """Test error handling with invalid file extension."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not a script")

        with pytest.raises(RunError):
            await run_flow(script_path=invalid_file)


# Example of how to create a test utility for common graph patterns
def create_test_graph_with_env_reader(tmp_path, env_var_name="TEST_VAR", default_value="default"):
    """Utility function to create a test graph that reads environment variables."""
    script_content = f"""
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output, Input
from lfx.schema.message import Message
from lfx.graph import Graph

class EnvReader(Component):
    inputs = [Input(name="trigger", input_types=["Message"], field_type="Message")]
    outputs = [Output(name="result", method="read_env", types=["Message"])]

    def read_env(self) -> Message:
        env_vars = self.graph.context.get("request_variables", {{}})
        value = env_vars.get("{env_var_name}", "{default_value}")
        return Message(text=f"{env_var_name}={{value}}")

chat_input = ChatInput()
env_reader = EnvReader()
env_reader.set(trigger=chat_input.message_response)
chat_output = ChatOutput().set(input_value=env_reader.read_env)

graph = Graph(chat_input, chat_output)
"""
    script_path = tmp_path / f"env_reader_{env_var_name.lower()}.py"
    script_path.write_text(script_content)
    return script_path


class TestRunFlowWithTestUtilities:
    """Tests using test utility functions for reduced code duplication."""

    @pytest.mark.asyncio
    async def test_env_reader_with_custom_var(self, tmp_path):
        """Test environment variable reading with custom variable name."""
        script_path = create_test_graph_with_env_reader(tmp_path, env_var_name="CUSTOM_VAR", default_value="not-set")

        result = await run_flow(
            script_path=script_path,
            global_variables={"CUSTOM_VAR": "custom-value"},
            verbose=False,
            check_variables=False,
        )

        assert result["success"] is True
        assert "CUSTOM_VAR=custom-value" in result["result"]

    @pytest.mark.asyncio
    async def test_env_reader_uses_default_when_missing(self, tmp_path):
        """Test that default values are used when env var is missing."""
        script_path = create_test_graph_with_env_reader(
            tmp_path, env_var_name="MISSING_VAR", default_value="default-used"
        )

        result = await run_flow(
            script_path=script_path,
            global_variables={},  # Empty env vars
            verbose=False,
            check_variables=False,
        )

        assert result["success"] is True
        assert "MISSING_VAR=default-used" in result["result"]
