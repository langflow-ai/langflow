"""Unit tests for the run command with environment variables."""

import json

import pytest
from lfx.__main__ import app
from typer.testing import CliRunner


class TestRunCommandEnvVar:
    """Unit tests for run command environment variable functionality."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    # app fixture not needed if importing global app

    @pytest.fixture
    def env_var_script(self, tmp_path):
        """Create a script that reads environment variables from graph context."""
        script_content = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output, Input
from lfx.schema.message import Message
from lfx.graph import Graph

class EnvReader(Component):
    inputs = [Input(name="trigger", input_types=["Message"], field_type="Message")]
    outputs = [Output(name="env_value", method="get_env_value", types=["Message"])]

    def get_env_value(self) -> Message:
        # Access request_variables from graph context
        request_variables = self.graph.context.get("request_variables", {})
        # Get TEST_VAR
        value = request_variables.get("TEST_VAR", "Not Found")
        return Message(text=f"Value: {value}")

chat_input = ChatInput()
env_reader = EnvReader()
# Connect input to trigger to ensure order (though not strictly necessary for this simple graph)
env_reader.set(trigger=chat_input.message_response)
# Use the method name for connection, not the output name
chat_output = ChatOutput().set(input_value=env_reader.get_env_value)

graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "env_var_script.py"
        script_path.write_text(script_content)
        return script_path

    def test_run_with_env_vars(self, runner, env_var_script):
        """Test running a flow with environment variables passed via CLI."""
        result = runner.invoke(
            app, ["run", str(env_var_script), "trigger", "--env-var", "TEST_VAR=my_secret_value", "--format", "json"]
        )

        if result.exit_code != 0:
            pytest.fail(f"Exit code {result.exit_code}. Output:\n{result.stdout}")

        # Verify output contains the injected value
        try:
            output_data = json.loads(result.stdout)
            if not output_data.get("success"):
                pytest.fail(f"Run failed: {json.dumps(output_data, indent=2)}")

            # The component outputs "Value: {value}"
            # Check recursively in result or text
            result_text = output_data.get("result", output_data.get("text", ""))
            assert "Value: my_secret_value" in str(result_text)
        except json.JSONDecodeError:
            pytest.fail(f"Output was not valid JSON: {result.stdout}")

    def test_run_with_multiple_env_vars(self, runner, tmp_path):
        """Test running with multiple environment variables."""
        script_content = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output, Input
from lfx.schema.message import Message
from lfx.graph import Graph

class MultiEnvReader(Component):
    inputs = [Input(name="trigger", input_types=["Message"], field_type="Message")]
    outputs = [Output(name="result", method="get_result", types=["Message"])]

    def get_result(self) -> Message:
        vars = self.graph.context.get("request_variables", {})
        v1 = vars.get("VAR1", "Missing1")
        v2 = vars.get("VAR2", "Missing2")
        return Message(text=f"{v1}|{v2}")

chat_input = ChatInput()
reader = MultiEnvReader().set(trigger=chat_input.message_response)
# Use the method name for connection
chat_output = ChatOutput().set(input_value=reader.get_result)

graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "multi_env.py"
        script_path.write_text(script_content)

        result = runner.invoke(
            app,
            ["run", str(script_path), "trigger", "--env-var", "VAR1=foo", "--env-var", "VAR2=bar", "--format", "json"],
        )

        if result.exit_code != 0:
            pytest.fail(f"Exit code {result.exit_code}. Output:\n{result.stdout}")
        try:
            output_data = json.loads(result.stdout)
            if not output_data.get("success"):
                pytest.fail(f"Run failed: {json.dumps(output_data, indent=2)}")
            result_text = output_data.get("result", "")
            assert "foo|bar" in str(result_text)
        except json.JSONDecodeError:
            pytest.fail(f"Output was not valid JSON: {result.stdout}")

    def test_invalid_env_var_format(self, runner, env_var_script):
        """Test that invalid env var format raises error."""
        result = runner.invoke(
            app,
            [
                "run",
                str(env_var_script),
                "test",
                "--env-var",
                "INVALID_FORMAT",  # Missing =
            ],
        )

        if result.exit_code != 1:
            pytest.fail(f"Expected exit code 1, got {result.exit_code}. Output:\n{result.stdout}")
        # Verify it's an error response
        try:
            output_data = json.loads(result.stdout)
            assert output_data["success"] is False
            assert "Invalid environment variable format" in output_data["exception_message"]
        except json.JSONDecodeError:
            # Fallback if output is raw text (should be JSON though)
            assert "Invalid environment variable format" in result.stdout
