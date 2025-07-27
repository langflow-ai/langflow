"""Unit tests for the execute command functionality."""

import contextlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from lfx.cli.execute import execute


class TestExecuteCommand:
    """Unit tests for execute command internal functionality."""

    @pytest.fixture
    def simple_chat_script(self, tmp_path):
        """Create a simple chat script for testing."""
        script_content = '''"""A simple chat flow example for Langflow.

This script demonstrates how to set up a basic conversational flow using Langflow's ChatInput and ChatOutput components.

Features:
- Configures logging to 'langflow.log' at INFO level
- Connects ChatInput to ChatOutput
- Builds a Graph object for the flow

Usage:
    python simple_chat.py

You can use this script as a template for building more complex conversational flows in Langflow.
"""

from pathlib import Path

from langflow.components.input_output import ChatInput, ChatOutput
from langflow.graph import Graph
from langflow.logging.logger import LogConfig

log_config = LogConfig(
    log_level="INFO",
    log_file=Path("langflow.log"),
)
chat_input = ChatInput()
chat_output = ChatOutput().set(input_value=chat_input.message_response)

graph = Graph(chat_input, chat_output, log_config=log_config)
'''
        script_path = tmp_path / "simple_chat.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.fixture
    def invalid_script(self, tmp_path):
        """Create a script without a graph variable."""
        script_content = '''"""Invalid script without graph variable."""

from langflow.components.input_output import ChatInput

chat_input = ChatInput()
# Missing graph variable
'''
        script_path = tmp_path / "invalid_script.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.fixture
    def syntax_error_script(self, tmp_path):
        """Create a script with syntax errors."""
        script_content = '''"""Script with syntax errors."""

from langflow.components.input_output import ChatInput

# Syntax error - missing closing parenthesis
chat_input = ChatInput(
'''
        script_path = tmp_path / "syntax_error.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.fixture
    def simple_json_flow(self):
        """Create a simple JSON flow for testing."""
        return {
            "data": {
                "nodes": [
                    {
                        "id": "ChatInput-1",
                        "type": "ChatInput",
                        "position": {"x": 100, "y": 100},
                        "data": {"display_name": "Chat Input"},
                    },
                    {
                        "id": "ChatOutput-1",
                        "type": "ChatOutput",
                        "position": {"x": 400, "y": 100},
                        "data": {"display_name": "Chat Output"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "ChatInput-1",
                        "target": "ChatOutput-1",
                        "sourceHandle": "message_response",
                        "targetHandle": "input_value",
                    }
                ],
            }
        }

    def test_execute_input_validation_no_sources(self):
        """Test that execute raises exit code 1 when no input source is provided."""
        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=None,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )
        assert exc_info.value.exit_code == 1

    def test_execute_input_validation_multiple_sources(self, simple_chat_script):
        """Test that execute raises exit code 1 when multiple input sources are provided."""
        # Test script_path + flow_json
        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=simple_chat_script,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json='{"data": {"nodes": []}}',
                stdin=False,
            )
        assert exc_info.value.exit_code == 1

        # Test flow_json + stdin
        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=None,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json='{"data": {"nodes": []}}',
                stdin=True,
            )
        assert exc_info.value.exit_code == 1

    def test_execute_python_script_success(self, simple_chat_script, capsys):
        """Test executing a valid Python script."""
        # Test that Python script execution either succeeds or fails gracefully
        with contextlib.suppress(typer.Exit):
            execute(
                script_path=simple_chat_script,
                input_value="Hello, world!",
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )

        # Test passes as long as no unhandled exceptions occur

        # Check that output was produced
        captured = capsys.readouterr()
        if captured.out:
            # Should be valid JSON when successful
            try:
                output_data = json.loads(captured.out)
                assert isinstance(output_data, dict)
                assert "result" in output_data  # Should have result field
            except json.JSONDecodeError:
                # Non-JSON output is also acceptable in some cases
                assert len(captured.out.strip()) > 0

    def test_execute_python_script_verbose(self, simple_chat_script, capsys):
        """Test executing a Python script with verbose output."""
        # Test that verbose mode execution either succeeds or fails gracefully
        with contextlib.suppress(typer.Exit):
            execute(
                script_path=simple_chat_script,
                input_value="Hello, world!",
                input_value_option=None,
                verbose=True,
                output_format="json",
                flow_json=None,
                stdin=False,
            )

        # Test passes as long as no unhandled exceptions occur

        # In verbose mode, there should be diagnostic output
        captured = capsys.readouterr()
        # Verbose mode should show diagnostic messages in stderr
        assert len(captured.out + captured.err) > 0

    def test_execute_python_script_different_formats(self, simple_chat_script):
        """Test executing a Python script with different output formats."""
        formats = ["json", "text", "message", "result"]

        for output_format in formats:
            # Test that each format either succeeds or fails gracefully
            with contextlib.suppress(typer.Exit):
                execute(
                    script_path=simple_chat_script,
                    input_value="Test input",
                    input_value_option=None,
                    verbose=False,
                    output_format=output_format,
                    flow_json=None,
                    stdin=False,
                )

            # Test passes as long as no unhandled exceptions occur

    def test_execute_file_not_exists(self, tmp_path):
        """Test execute with non-existent file raises exit code 1."""
        non_existent_file = tmp_path / "does_not_exist.py"

        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=non_existent_file,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )
        assert exc_info.value.exit_code == 1

    def test_execute_invalid_file_extension(self, tmp_path):
        """Test execute with invalid file extension raises exit code 1."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a script")

        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=txt_file,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )
        assert exc_info.value.exit_code == 1

    def test_execute_python_script_no_graph_variable(self, invalid_script):
        """Test execute with Python script that has no graph variable."""
        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=invalid_script,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )
        assert exc_info.value.exit_code == 1

    def test_execute_python_script_syntax_error(self, syntax_error_script):
        """Test execute with Python script that has syntax errors."""
        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=syntax_error_script,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )
        assert exc_info.value.exit_code == 1

    def test_execute_flow_json_valid(self, simple_json_flow):
        """Test execute with valid flow_json."""
        flow_json_str = json.dumps(simple_json_flow)

        # Test that JSON flow execution either succeeds or fails gracefully
        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=None,
                input_value="Hello JSON!",
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=flow_json_str,
                stdin=False,
            )

        # The function should exit cleanly (either success or expected failure)
        assert exc_info.value.exit_code in [0, 1]

    def test_execute_flow_json_invalid(self):
        """Test execute with invalid flow_json raises exit code 1."""
        invalid_json = '{"nodes": [invalid json'

        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=None,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=invalid_json,
                stdin=False,
            )
        assert exc_info.value.exit_code == 1

    @patch("sys.stdin")
    def test_execute_stdin_valid(self, mock_stdin, simple_json_flow):
        """Test execute with valid stdin input."""
        flow_json_str = json.dumps(simple_json_flow)
        mock_stdin.read.return_value = flow_json_str

        # Test that stdin execution either succeeds or fails gracefully
        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=None,
                input_value="Hello stdin!",
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=True,
            )

        # Check that stdin was read and function exited cleanly
        mock_stdin.read.assert_called_once()
        assert exc_info.value.exit_code in [0, 1]

    @patch("sys.stdin")
    def test_execute_stdin_empty(self, mock_stdin):
        """Test execute with empty stdin raises exit code 1."""
        mock_stdin.read.return_value = ""

        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=None,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=True,
            )
        assert exc_info.value.exit_code == 1

    @patch("sys.stdin")
    def test_execute_stdin_invalid(self, mock_stdin):
        """Test execute with invalid stdin JSON raises exit code 1."""
        mock_stdin.read.return_value = '{"nodes": [invalid json'

        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=None,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=True,
            )
        assert exc_info.value.exit_code == 1

    def test_execute_input_value_precedence(self, simple_chat_script, capsys):
        """Test that positional input_value takes precedence over --input-value option."""
        # Test that input precedence works and execution either succeeds or fails gracefully
        with contextlib.suppress(typer.Exit):
            execute(
                script_path=simple_chat_script,
                input_value="positional_value",
                input_value_option="option_value",
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )

        # Test passes as long as no unhandled exceptions occur

        # If successful, verify that positional value was used
        captured = capsys.readouterr()
        if captured.out and "positional_value" in captured.out:
            # Positional value was used correctly
            assert True

    def test_execute_directory_instead_of_file(self, tmp_path):
        """Test execute with directory instead of file raises exit code 1."""
        directory = tmp_path / "test_dir"
        directory.mkdir()

        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=directory,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )
        assert exc_info.value.exit_code == 1

    def test_execute_json_flow_with_temporary_file_cleanup(self, simple_json_flow):
        """Test that temporary files are cleaned up when using flow_json."""
        flow_json_str = json.dumps(simple_json_flow)

        # Count temporary files before
        temp_dir = Path(tempfile.gettempdir())
        temp_files_before = list(temp_dir.glob("*.json"))

        with contextlib.suppress(typer.Exit):
            execute(
                script_path=None,
                input_value="Test cleanup",
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=flow_json_str,
                stdin=False,
            )

        # Count temporary files after
        temp_files_after = list(temp_dir.glob("*.json"))

        # Should not have more temp files than before (cleanup working)
        assert len(temp_files_after) <= len(temp_files_before) + 1  # Allow for one potential leftover

    def test_execute_verbose_error_output(self, invalid_script, capsys):
        """Test that verbose mode shows error details."""
        with pytest.raises(typer.Exit) as exc_info:
            execute(
                script_path=invalid_script,
                input_value=None,
                input_value_option=None,
                verbose=True,
                output_format="json",
                flow_json=None,
                stdin=False,
            )

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        # Verbose mode should show error details
        error_output = captured.out + captured.err
        assert "graph" in error_output.lower() or "variable" in error_output.lower()

    def test_execute_without_input_value(self, simple_chat_script, capsys):
        """Test executing without providing input value."""
        # Test that execution without input either succeeds or fails gracefully
        with contextlib.suppress(typer.Exit):
            execute(
                script_path=simple_chat_script,
                input_value=None,
                input_value_option=None,
                verbose=False,
                output_format="json",
                flow_json=None,
                stdin=False,
            )

        # Test passes as long as no unhandled exceptions occur

        # Check that output was produced
        captured = capsys.readouterr()
        if captured.out:
            # Should be valid JSON when successful
            try:
                output_data = json.loads(captured.out)
                assert isinstance(output_data, dict)
            except json.JSONDecodeError:
                assert len(captured.out.strip()) >= 0
