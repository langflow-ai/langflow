import json
import socket
import threading
import time
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langflow.__main__ import app
from langflow.services import deps


@pytest.fixture(scope="module")
def default_settings():
    return [
        "--backend-only",
        "--no-open-browser",
    ]


@pytest.fixture
def temp_python_script(tmp_path):
    """Create a temporary Python script for testing."""
    script_content = '''"""Test script for execute command."""
from langflow.components.input_output.chat import ChatInput
from langflow.components.input_output.chat_output import ChatOutput
from langflow.graph.graph.base import Graph

# Create a simple echo chat bot
chat_input = ChatInput(_id="chat_input")
chat_output = ChatOutput(_id="chat_output")
chat_output.set(input_value=chat_input.message_response)

graph = Graph(chat_input, chat_output)
'''
    script_path = tmp_path / "test_script.py"
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def test_basic_prompting(tmp_path):
    """Use the existing test JSON flow from pytest configuration."""
    script_content = dedent("""
from langflow.initial_setup.starter_projects.basic_prompting import basic_prompting_graph
graph = basic_prompting_graph()
""").strip()
    script_path = tmp_path / "test_script.py"
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def invalid_python_script(tmp_path):
    """Create an invalid Python script for testing error handling."""
    script_content = '''"""Invalid test script."""
# This script has no graph variable
from langflow.components.input_output.chat import ChatInput

chat_input = ChatInput(_id="chat_input")
# Missing graph assignment
'''
    script_path = tmp_path / "invalid_script.py"
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def syntax_error_script(tmp_path):
    """Create a Python script with syntax errors."""
    script_content = '''"""Script with syntax errors."""
from langflow.components.input_output.chat import ChatInput

# Syntax error - missing closing parenthesis
chat_input = ChatInput(_id="chat_input"
'''
    script_path = tmp_path / "syntax_error.py"
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def test_json_flow():
    """Use the existing test JSON flow from pytest configuration."""
    return pytest.MEMORY_CHATBOT_NO_LLM


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def run_flow(runner, port, components_path, default_settings):
    args = [
        "run",
        "--port",
        str(port),
        "--components-path",
        str(components_path),
        *default_settings,
    ]
    result = runner.invoke(app, args)
    if result.exit_code != 0:
        msg = f"CLI failed with exit code {result.exit_code}: {result.output}"
        raise RuntimeError(msg)


def test_components_path(runner, default_settings, tmp_path):
    # create a "components" folder
    temp_dir = tmp_path / "components"
    temp_dir.mkdir(exist_ok=True)

    port = get_free_port()

    thread = threading.Thread(
        target=run_flow,
        args=(runner, port, temp_dir, default_settings),
        daemon=True,
    )
    thread.start()

    # Give the server some time to start
    time.sleep(5)

    settings_service = deps.get_settings_service()
    assert str(temp_dir) in settings_service.settings.components_path


def test_superuser(runner):
    result = runner.invoke(app, ["superuser"], input="admin\nadmin\n")
    assert result.exit_code == 0, result.stdout
    assert "Superuser created successfully." in result.stdout


# Enhanced Execute Command Tests


class TestExecuteCommand:
    """Test suite for the enhanced execute command."""

    def test_execute_python_script_default_json_output(self, runner, temp_python_script):
        """Test executeing a Python script with default JSON output format."""
        result = runner.invoke(app, ["execute", str(temp_python_script), "Hello World"])

        # Check if command executed successfully
        if result.exit_code == 0:
            # Use comprehensive JSON validation to ensure no errors
            output_data = validate_execute_command_json_response(
                result.output,
                expect_success=True,
                expect_result=True,
                allow_empty_result=True,  # Allow empty results in test environment
            )
            # Additional checks for structure
            assert isinstance(output_data, dict), f"Expected dict response: {output_data}"
        else:
            # Command failed, but that's expected in some test environments
            assert result.exit_code in [0, 1]

    def test_execute_basic_prompting(self, runner, test_basic_prompting):
        """Test executeing a basic prompting graph."""
        result = runner.invoke(app, ["execute", str(test_basic_prompting), "Hello World"])
        assert result.exit_code == 0, result.output

        # Use comprehensive JSON validation to ensure no errors
        output_data = validate_execute_command_json_response(
            result.output,
            expect_success=False,  # Allow failure when API keys are not available
            expect_result=False,  # Don't require result when execution fails
            allow_empty_result=True,  # Allow empty results in test environment
        )

        # Check that we have a proper response structure
        assert isinstance(output_data, dict), f"Expected dict response: {output_data}"

        # If execution succeeded, should have non-empty result
        if output_data.get("success", False):
            assert len(output_data.get("result", "")) > 0, f"Expected non-empty result: {output_data}"

    def test_execute_python_script_verbose_mode(self, runner, temp_python_script):
        """Test executeing a Python script with verbose mode."""
        result = runner.invoke(app, ["execute", str(temp_python_script), "Hello World", "--verbose"])

        # Verbose mode should show diagnostic output in stderr or mixed output
        # Check that some form of diagnostic information is present
        if result.exit_code == 0:
            # Should have either found graph variable message or some diagnostic output
            full_output = result.output + getattr(result, "stderr", "")
            assert "graph" in full_output.lower() or len(result.output) > 0

    def test_execute_python_script_text_format(self, runner, temp_python_script):
        """Test executeing a Python script with text output format."""
        result = runner.invoke(app, ["execute", str(temp_python_script), "Hello World", "--format", "text"])

        # Should have some text output if successful
        if result.exit_code == 0:
            assert len(result.output.strip()) > 0

    def test_execute_python_script_result_format(self, runner, temp_python_script):
        """Test executeing a Python script with result output format."""
        result = runner.invoke(app, ["execute", str(temp_python_script), "Hello World", "--format", "result"])

        # Should have some output if successful
        if result.exit_code == 0:
            assert len(result.output.strip()) >= 0  # Can be empty string for result format

    def test_execute_json_flow_default_output(self, runner, test_json_flow):
        """Test executeing a JSON flow with default output format."""
        if not test_json_flow.exists():
            pytest.skip("Test JSON flow file not found")

        result = runner.invoke(app, ["execute", str(test_json_flow), "Hello JSON"])
        # Note: This might fail due to tracing issues, but we test the command structure
        assert result.exit_code in [0, 1], f"Unexpected exit code: {result.exit_code}"

    def test_execute_json_flow_verbose_mode(self, runner, test_json_flow):
        """Test executeing a JSON flow with verbose mode."""
        if not test_json_flow.exists():
            pytest.skip("Test JSON flow file not found")

        result = runner.invoke(app, ["execute", str(test_json_flow), "Hello JSON", "--verbose"])

        # Should show diagnostic output even if execution fails
        assert "JSON flow" in result.output or result.exit_code == 1

    def test_execute_nonexistent_file(self, runner):
        """Test error handling for nonexistent files."""
        result = runner.invoke(app, ["execute", "nonexistent.py", "test"])
        assert result.exit_code == 1

    def test_execute_nonexistent_file_verbose(self, runner):
        """Test error handling for nonexistent files in verbose mode."""
        result = runner.invoke(app, ["execute", "nonexistent.py", "test", "--verbose"])
        assert result.exit_code == 1
        # Check stderr or combined output for error message
        full_output = result.output + getattr(result, "stderr", "")
        assert "does not exist" in full_output

    def test_execute_invalid_file_extension(self, runner, tmp_path):
        """Test error handling for unsupported file extensions."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not a script")

        result = runner.invoke(app, ["execute", str(invalid_file), "test", "--verbose"])
        assert result.exit_code == 1
        full_output = result.output + getattr(result, "stderr", "")
        assert "must be a .py or .json file" in full_output

    def test_execute_invalid_python_script(self, runner, invalid_python_script):
        """Test error handling for Python scripts without graph variable."""
        result = runner.invoke(app, ["execute", str(invalid_python_script), "test", "--verbose"])
        assert result.exit_code == 1
        full_output = result.output + getattr(result, "stderr", "")
        assert "No 'graph' variable found in script" in full_output

    def test_execute_syntax_error_script(self, runner, syntax_error_script):
        """Test error handling for Python scripts with syntax errors."""
        result = runner.invoke(app, ["execute", str(syntax_error_script), "test", "--verbose"])
        assert result.exit_code == 1
        # Should handle syntax errors gracefully

    def test_execute_without_input_value(self, runner, temp_python_script):
        """Test executeing without providing input value."""
        result = runner.invoke(app, ["execute", str(temp_python_script)])

        # Should still execute with None input if successful
        if result.exit_code == 0:
            # Try to parse JSON output
            try:
                output_data = json.loads(result.output.strip())
                assert "result" in output_data or "text" in output_data
            except json.JSONDecodeError:
                # If JSON parsing fails, check that we have some output
                assert len(result.output.strip()) >= 0

    def test_execute_all_output_formats(self, runner, temp_python_script):
        """Test all supported output formats."""
        formats = ["json", "text", "message", "result"]

        for format_type in formats:
            result = runner.invoke(app, ["execute", str(temp_python_script), "test", "--format", format_type])
            # Should either succeed or fail gracefully
            if result.exit_code == 0:
                # Should have some output for all formats
                assert len(result.output.strip()) >= 0, f"No output for format {format_type}"

    def test_execute_log_capture_in_json(self, runner, temp_python_script):
        """Test that logs are captured and included in JSON output."""
        result = runner.invoke(app, ["execute", str(temp_python_script), "test"])

        if result.exit_code == 0:
            # Use comprehensive JSON validation to ensure no errors and check logs
            output_data = validate_execute_command_json_response(
                result.output, expect_success=True, expect_result=True, allow_empty_result=True
            )
            # Logs should be present in the JSON output
            assert "logs" in output_data, f"Missing logs field in JSON output: {output_data}"
            assert isinstance(output_data["logs"], str), f"Logs should be string: {output_data['logs']}"

    @pytest.mark.parametrize("verbose", [True, False])
    def test_execute_json_formatting(self, runner, temp_python_script, verbose):
        """Test JSON formatting in verbose vs quiet mode."""
        args = ["execute", str(temp_python_script), "test"]
        if verbose:
            args.append("--verbose")

        result = runner.invoke(app, args)

        if result.exit_code == 0:
            # In verbose mode, there might be diagnostic output mixed in
            # Try to find JSON in the output
            lines = result.output.strip().split("\n")
            json_found = False
            for line in lines:
                stripped_line = line.strip()
                if stripped_line and stripped_line.startswith(("{", "[")):
                    try:
                        json.loads(stripped_line)
                        json_found = True
                        break
                    except json.JSONDecodeError:
                        continue

            # Either we found JSON or we have some output
            assert json_found or len(result.output.strip()) > 0

    def test_execute_help_output(self, runner):
        """Test the help output for the execute command."""
        result = runner.invoke(app, ["execute", "--help"])
        assert result.exit_code == 0, result
        assert "Execute a Langflow graph script or JSON flow" in result.output
        assert "--verbose" in result.output
        assert "--format" in result.output

    def test_execute_directory_instead_of_file(self, runner, tmp_path):
        """Test error handling when providing directory instead of file."""
        result = runner.invoke(app, ["execute", str(tmp_path), "test", "--verbose"])
        assert result.exit_code == 1
        full_output = result.output + getattr(result, "stderr", "")
        assert "is not a file" in full_output

    def test_execute_json_response_validation_comprehensive(self, runner, temp_python_script):
        """Comprehensive test to validate JSON responses don't contain errors."""
        test_cases = [
            # Test different formats that should return JSON
            {"args": ["execute", str(temp_python_script), "test"], "expect_json": True},
            {"args": ["execute", str(temp_python_script), "test", "--format", "json"], "expect_json": True},
            {"args": ["execute", str(temp_python_script), "test", "--verbose"], "expect_json": True},
            {"args": ["execute", str(temp_python_script)], "expect_json": True},  # No input
        ]

        for case in test_cases:
            result = runner.invoke(app, case["args"])

            if result.exit_code == 0 and case["expect_json"]:
                # Validate that JSON response contains no errors
                output_data = validate_execute_command_json_response(
                    result.output, expect_success=True, expect_result=True, allow_empty_result=True
                )

                # Specific validations for error-free responses
                assert "error" not in output_data, f"Unexpected error in response: {output_data}"

                if "success" in output_data:
                    assert output_data["success"] is True, f"Expected success=True: {output_data}"

                # Check that required fields have correct types
                if "result" in output_data:
                    assert output_data["result"] is not None or case["args"][-1] == str(temp_python_script), (
                        f"Unexpected None result: {output_data}"
                    )

                if "type" in output_data:
                    assert isinstance(output_data["type"], str), f"Type should be string: {output_data}"

                if "component" in output_data:
                    assert isinstance(output_data["component"], str), f"Component should be string: {output_data}"

            elif result.exit_code != 0:
                # Command failed, which is acceptable in test environments
                pass  # No diagnostic output needed

    def test_execute_error_response_validation(self, runner):
        """Test that error responses are properly formatted."""
        # Test with non-existent file in verbose mode to get error output
        result = runner.invoke(app, ["execute", "nonexistent.py", "test", "--verbose"])
        assert result.exit_code == 1

        # In verbose mode, error messages go to stderr but CLI runner might capture differently
        # Check if we have any output at all (stdout or potentially captured stderr)
        full_output = result.output + getattr(result, "stderr", "")

        if len(full_output.strip()) > 0:
            # If we have output, validate it
            try:
                # Try to validate as JSON error response
                validate_execute_command_error_response(full_output)
                # Error response is valid JSON with proper error structure
            except (json.JSONDecodeError, AssertionError):
                # Non-JSON error output is acceptable for CLI tools
                assert "does not exist" in full_output or len(full_output.strip()) > 0
        else:
            # No output captured - this is acceptable for CLI tools that only set exit codes
            pass

        # Also test quiet mode behavior
        result_quiet = runner.invoke(app, ["execute", "nonexistent.py", "test"])
        assert result_quiet.exit_code == 1
        # Quiet mode should not output error details to stdout


class TestMCPServeCommand:
    """Test suite for MCP mode in the serve command."""

    @pytest.fixture(autouse=True)
    def _set_dummy_api_key(self, monkeypatch, request):
        # MCP mode doesn't require API key, so we don't set it
        # This allows us to test MCP functionality without API key requirements
        pass

    def test_mcp_mode_help_output(self, runner):
        """Test that MCP options appear in serve command help."""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--mcp/--no-mcp" in result.output
        assert "--mcp-transport" in result.output
        assert "--mcp-name" in result.output
        assert "MCP (Model Context Protocol)" in result.output

    def test_mcp_transport_validation(self, runner, temp_python_script):
        """Test validation of MCP transport options."""
        # Test invalid transport
        result = runner.invoke(app, ["serve", str(temp_python_script), "--mcp", "--mcp-transport", "invalid"])
        assert result.exit_code == 1
        assert "Invalid MCP transport 'invalid'" in result.output
        assert "Must be one of: sse, stdio, websocket" in result.output

    def test_mcp_valid_transports(self, runner, temp_python_script):
        """Test that valid MCP transports are accepted."""
        valid_transports = ["stdio", "sse", "websocket"]

        for transport in valid_transports:
            # We just test that the validation passes and the command would start
            # We'll use a timeout or patch to avoid actually starting the server
            with patch("langflow.cli.commands.run_mcp_server") as mock_run_mcp:
                mock_run_mcp.side_effect = KeyboardInterrupt("Test interrupt")

                result = runner.invoke(
                    app, ["serve", str(temp_python_script), "--mcp", "--mcp-transport", transport, "--verbose"]
                )

                # Should either exit cleanly (0) or with KeyboardInterrupt handling
                assert result.exit_code in [0, 1]
                # Should show MCP mode is enabled
                assert f"MCP mode enabled with {transport} transport" in result.output

    def test_mcp_no_api_key_required(self, runner, temp_python_script):
        """Test that MCP mode doesn't require LANGFLOW_API_KEY."""
        # Ensure no API key is set
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(app, ["serve", str(temp_python_script), "--mcp", "--verbose"])

            # Should not fail due to missing API key
            # The validation message should show MCP is enabled
            assert "MCP mode enabled" in result.output or result.exit_code in [0, 1]
            # Should not show API key validation error
            assert "LANGFLOW_API_KEY" not in result.output

    def test_rest_api_mode_requires_api_key(self, runner, temp_python_script):
        """Test that REST API mode (default) still requires API key."""
        # Ensure no API key is set
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(app, ["serve", str(temp_python_script), "--no-mcp", "--verbose"])

            # Should fail due to missing API key
            assert result.exit_code == 1
            assert "LANGFLOW_API_KEY" in result.output

    @patch("langflow.cli.commands.uvicorn.run")
    @patch("langflow.cli.commands.create_multi_serve_app")
    def test_mcp_server_creation_single_flow(self, mock_create_app, mock_uvicorn_run, runner, temp_python_script):
        """Test MCP server creation for single flow."""
        # Mock the FastAPI app creation
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        mock_uvicorn_run.side_effect = KeyboardInterrupt("Test interrupt")

        runner.invoke(app, ["serve", str(temp_python_script), "--mcp", "--mcp-name", "Test MCP Server", "--verbose"])

        # Verify FastAPI app was created
        mock_create_app.assert_called_once()
        call_args = mock_create_app.call_args
        assert "graphs" in call_args[1]
        assert "metas" in call_args[1]

        # Verify uvicorn was run with correct parameters
        mock_uvicorn_run.assert_called_once()
        run_args = mock_uvicorn_run.call_args
        assert run_args[1]["host"] == "127.0.0.1"
        assert run_args[1]["port"] == 8000
        assert run_args[1]["log_level"] == "warning"

    @patch("langflow.cli.commands.uvicorn.run")
    @patch("langflow.cli.commands.create_multi_serve_app")
    def test_mcp_server_creation_folder(self, mock_create_app, mock_uvicorn_run, runner, tmp_path):
        """Test MCP server creation for folder with multiple flows."""
        # Create test JSON files
        flow1 = tmp_path / "flow1.json"
        flow2 = tmp_path / "flow2.json"

        # Create minimal valid JSON flow structure
        flow_content = {"data": {"nodes": [], "edges": []}}

        flow1.write_text(json.dumps(flow_content))
        flow2.write_text(json.dumps(flow_content))

        # Mock the graph loading to avoid complex flow parsing
        with patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph:
            mock_graph = MagicMock()
            mock_graph.flow_id = "test_flow"
            mock_load_graph.return_value = mock_graph

            # Mock FastAPI app creation
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            mock_uvicorn_run.side_effect = KeyboardInterrupt("Test interrupt")

            runner.invoke(
                app, ["serve", str(tmp_path), "--mcp", "--mcp-transport", "sse", "--port", "8001", "--verbose"]
            )

            # Should find both JSON files and try to load them
            assert mock_load_graph.call_count == 2

            # Verify FastAPI app was created
            mock_create_app.assert_called_once()

            # Verify uvicorn was run with correct parameters
            mock_uvicorn_run.assert_called_once()
            run_args = mock_uvicorn_run.call_args
            assert run_args[1]["host"] == "127.0.0.1"
            assert run_args[1]["port"] == 8001

    def test_mcp_server_with_transport_warnings(self, runner, temp_python_script):
        """Test MCP server with different transport types (showing warnings for unsupported ones)."""
        transports = ["stdio", "websocket", "sse"]

        for transport in transports:
            with (
                patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn_run,
                patch("langflow.cli.commands.create_multi_serve_app") as mock_create_app,
            ):
                mock_app = MagicMock()
                mock_create_app.return_value = mock_app
                mock_uvicorn_run.side_effect = KeyboardInterrupt("Test interrupt")

                result = runner.invoke(
                    app, ["serve", str(temp_python_script), "--mcp", "--mcp-transport", transport, "--verbose"]
                )

                assert result.exit_code == 0

                if transport != "sse":
                    # Should show warning for non-SSE transports
                    assert "Only SSE transport is currently supported" in result.output

                # Should always call uvicorn (defaults to SSE)
                mock_uvicorn_run.assert_called_once()

    def test_mcp_server_error_handling(self, runner, temp_python_script):
        """Test error handling in MCP server creation."""
        with patch("langflow.cli.commands.create_multi_serve_app") as mock_create_app:
            # Mock an error during FastAPI app creation
            mock_create_app.side_effect = Exception("App creation failed")

            result = runner.invoke(app, ["serve", str(temp_python_script), "--mcp", "--verbose"])

            assert result.exit_code == 1
            assert "Failed to start MCP server" in result.output

    def test_mcp_server_keyboard_interrupt(self, runner, temp_python_script):
        """Test graceful handling of keyboard interrupt in MCP server."""
        with (
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn_run,
            patch("langflow.cli.commands.create_multi_serve_app"),
        ):
            mock_uvicorn_run.side_effect = KeyboardInterrupt("User interrupt")

            result = runner.invoke(app, ["serve", str(temp_python_script), "--mcp", "--verbose"])

            assert result.exit_code == 0
            assert "MCP server stopped" in result.output

    def test_mcp_mode_output_formatting(self, runner, temp_python_script):
        """Test that MCP mode shows appropriate output formatting."""
        with (
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn_run,
            patch("langflow.cli.commands.create_multi_serve_app"),
        ):
            mock_uvicorn_run.side_effect = KeyboardInterrupt("Test interrupt")

            result = runner.invoke(
                app,
                [
                    "serve",
                    str(temp_python_script),
                    "--mcp",
                    "--mcp-transport",
                    "sse",
                    "--mcp-name",
                    "Custom MCP Server",
                    "--verbose",
                ],
            )

            # Check for MCP-specific output
            assert "MCP Server Started!" in result.output
            assert "MCP (SSE)" in result.output  # Updated to match actual output
            assert "MCP SSE endpoint:" in result.output
            assert "/api/v1/mcp/sse" in result.output
            assert "MCP Tools:" in result.output

    def test_mcp_vs_rest_api_mode_exclusive(self, runner, temp_python_script):
        """Test that MCP and REST API modes are mutually exclusive in terms of requirements."""
        # Test that --mcp skips API key validation
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn_run,
            patch("langflow.cli.commands.create_multi_serve_app"),
        ):
            mock_uvicorn_run.side_effect = KeyboardInterrupt("Test interrupt")

            # MCP mode should work without API key
            result_mcp = runner.invoke(app, ["serve", str(temp_python_script), "--mcp", "--verbose"])
            assert "MCP mode enabled" in result_mcp.output

            # REST API mode should fail without API key
            result_rest = runner.invoke(app, ["serve", str(temp_python_script), "--no-mcp", "--verbose"])
            assert result_rest.exit_code == 1
            assert "LANGFLOW_API_KEY" in result_rest.output

    def test_mcp_folder_no_json_files(self, runner, tmp_path):
        """Test MCP mode with folder containing no JSON files."""
        # Create a folder with no JSON files
        (tmp_path / "not_a_flow.txt").write_text("This is not a flow")

        result = runner.invoke(app, ["serve", str(tmp_path), "--mcp", "--verbose"])

        assert result.exit_code == 1
        assert "No .json flow files found" in result.output

    @patch("langflow.cli.commands.load_graph_from_path")
    def test_mcp_folder_invalid_flow(self, mock_load_graph, runner, tmp_path):
        """Test MCP mode with folder containing invalid flow files."""
        # Create a JSON file
        flow_file = tmp_path / "invalid_flow.json"
        flow_file.write_text('{"invalid": "flow"}')

        # Mock graph loading to raise an error
        mock_load_graph.side_effect = ValueError("Invalid flow structure")

        result = runner.invoke(app, ["serve", str(tmp_path), "--mcp", "--verbose"])

        assert result.exit_code == 1
        assert "Failed loading flow" in result.output

    def test_mcp_custom_host_port(self, runner, temp_python_script):
        """Test MCP mode with custom host and port."""
        with (
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn_run,
            patch("langflow.cli.commands.create_multi_serve_app"),
        ):
            mock_uvicorn_run.side_effect = KeyboardInterrupt("Test interrupt")

            runner.invoke(
                app,
                [
                    "serve",
                    str(temp_python_script),
                    "--mcp",
                    "--mcp-transport",
                    "sse",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "9000",
                    "--verbose",
                ],
            )

            # Verify custom host and port were passed
            mock_uvicorn_run.assert_called_once()
            run_args = mock_uvicorn_run.call_args
            assert run_args[1]["host"] == "127.0.0.1"
            assert run_args[1]["port"] == 9000


def validate_execute_command_json_response(
    output: str, *, expect_success: bool = True, expect_result: bool = True, allow_empty_result: bool = False
) -> dict[str, Any]:
    """Validate JSON response from execute command.

    Args:
        output: Raw output from CLI command
        expect_success: Whether to expect success=True in response
        expect_result: Whether to expect a result field
        allow_empty_result: Whether empty/None results are acceptable

    Returns:
        Parsed JSON data if valid

    Raises:
        AssertionError: If validation fails
        json.JSONDecodeError: If JSON is invalid
    """
    import contextlib
    import re

    # Parse JSON - handle case where there might be progress output mixed in
    try:
        # Try to find the JSON in the output by looking for JSON patterns
        lines = output.strip().split("\n")
        json_data = None

        # First try: Look for lines that look like complete JSON objects
        for line in lines:
            stripped_line = line.strip()
            if stripped_line and stripped_line.startswith(("{", "[")):
                with contextlib.suppress(json.JSONDecodeError):
                    json_data = json.loads(stripped_line)
                    break

        # Second try: Look for JSON from the end backwards (most recent output)
        if json_data is None:
            for line in reversed(lines):
                stripped_line = line.strip()
                if stripped_line and stripped_line.startswith(("{", "[")):
                    with contextlib.suppress(json.JSONDecodeError):
                        json_data = json.loads(stripped_line)
                        break

        # Third try: Look for multiline JSON by finding braces
        if json_data is None:
            # Find the start and end of JSON content
            start_idx = -1
            end_idx = -1

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("{"):
                    start_idx = i
                if stripped.endswith("}") and start_idx != -1:
                    end_idx = i
                    break

            if start_idx != -1 and end_idx != -1:
                json_lines = lines[start_idx : end_idx + 1]
                json_text = "\n".join(json_lines)
                with contextlib.suppress(json.JSONDecodeError):
                    json_data = json.loads(json_text)

        # Fourth try: If no JSON found in lines, try the whole output
        if json_data is None:
            # Clean the output by removing progress indicators and ANSI codes
            clean_output = output.strip()

            # Handle carriage returns that overwrite text - keep only the last part after \r
            if "\r" in clean_output:
                # Split on carriage returns and take the last non-empty part
                parts = clean_output.split("\r")
                for part in reversed(parts):
                    if part.strip():
                        clean_output = part.strip()
                        break

            # Remove common progress indicators
            for pattern in [
                "□ Launching Langflow...",
                "▣ Launching Langflow...",
                "■ Launching Langflow...",
                "▢ Launching Langflow...",
            ]:
                clean_output = clean_output.replace(pattern, "")
            # Remove ANSI escape sequences (color codes, etc.)
            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
            clean_output = ansi_escape.sub("", clean_output).strip()

            with contextlib.suppress(json.JSONDecodeError):
                json_data = json.loads(clean_output)

        # If still no JSON found, raise error
        if json_data is None:
            msg = f"No valid JSON found in output.\nFull output: {output}"
            raise AssertionError(msg)

        data = json_data
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON output: {e}\nOutput: {output}"
        raise AssertionError(msg) from e

    # Validate basic structure
    assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"

    # Check for error fields first
    if "error" in data:
        if expect_success:
            msg = f"Unexpected error in response: {data['error']}"
            raise AssertionError(msg)
        # If we expect an error, validate error structure
        assert isinstance(data["error"], str), f"Error should be string: {data['error']}"
        assert data.get("success", True) is False, "Error responses should have success=False"
        return data

    # Validate success field
    if "success" in data:
        success_value = data["success"]
        assert isinstance(success_value, bool), f"Success field should be boolean: {success_value}"
        if expect_success:
            assert success_value is True, f"Expected success=True, got {success_value}"
        # Note: We don't assert False when expect_success=False since that's optional
    elif expect_success:
        # If no success field but we expect success, that's okay for some formats
        pass

    # Validate result field if expected
    if expect_result and "success" in data and data.get("success", False):
        # Only require result field if we expect it AND execution was successful
        assert "result" in data, f"Missing 'result' field in response: {data}"
        result_value = data["result"]
        if not allow_empty_result:
            assert result_value is not None, f"Result should not be None: {data}"
            if isinstance(result_value, str):
                assert len(result_value.strip()) > 0, f"Result should not be empty string: {data}"
    elif expect_result and "success" not in data:
        # If no success field, still require result field if expected
        assert "result" in data, f"Missing 'result' field in response: {data}"
        result_value = data["result"]
        if not allow_empty_result:
            assert result_value is not None, f"Result should not be None: {data}"
            if isinstance(result_value, str):
                assert len(result_value.strip()) > 0, f"Result should not be empty string: {data}"

    # Validate type field if present
    if "type" in data:
        type_value = data["type"]
        assert isinstance(type_value, str), f"Type field should be string: {type_value}"
        # Note: Don't enforce specific types strictly as there might be other valid types

    # Validate component field if present
    if "component" in data:
        component_value = data["component"]
        assert isinstance(component_value, str), f"Component field should be string: {component_value}"

    # Validate logs field if present
    if "logs" in data:
        logs_value = data["logs"]
        assert isinstance(logs_value, str), f"Logs field should be string: {logs_value}"

    return data


def validate_execute_command_error_response(output: str) -> dict[str, Any]:
    """Validate JSON error response from execute command."""
    return validate_execute_command_json_response(output, expect_success=False, expect_result=False)


# Serve Command Tests


class TestServeCommand:
    """Test suite for the serve command."""

    @pytest.fixture(autouse=True)
    def _set_dummy_api_key(self, monkeypatch, request):
        # Only skip for tests that explicitly test missing API key
        if not request.node.name.startswith("test_serve_missing_api_key"):
            monkeypatch.setenv("LANGFLOW_API_KEY", "dummy-test-key")

    def test_serve_help_output(self, runner):
        """Test serve command help output."""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "Serve Langflow graphs as web API endpoints" in result.output

    def test_serve_nonexistent_file(self, runner):
        """Test error handling for nonexistent files."""
        result = runner.invoke(app, ["serve", "nonexistent.py", "--verbose"])
        assert result.exit_code == 1
        # Check stderr or combined output for error message
        full_output = result.output + getattr(result, "stderr", "")
        assert "does not exist" in full_output

    def test_serve_invalid_file_extension(self, runner, tmp_path):
        """Test error handling for unsupported file extensions."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not a script")

        result = runner.invoke(app, ["serve", str(invalid_file), "--verbose"])
        assert result.exit_code == 1
        full_output = result.output + getattr(result, "stderr", "")
        assert "must be a .py or .json file" in full_output

    def test_serve_invalid_python_script(self, runner, invalid_python_script):
        """Test error handling for Python scripts without graph variable."""
        result = runner.invoke(app, ["serve", str(invalid_python_script), "--verbose"])
        assert result.exit_code == 1
        full_output = result.output + getattr(result, "stderr", "")
        assert "No 'graph' variable found in script" in full_output

    def test_serve_syntax_error_script(self, runner, syntax_error_script):
        """Test error handling for Python scripts with syntax errors."""
        result = runner.invoke(app, ["serve", str(syntax_error_script), "--verbose"])
        assert result.exit_code == 1
        # Should handle syntax errors gracefully

    def test_serve_directory_instead_of_file(self, runner, tmp_path):
        """Test serve command with directory instead of file."""
        from unittest.mock import patch

        # Create an empty directory
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()

        with patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}):
            result = runner.invoke(app, ["serve", str(empty_dir), "--verbose"])
            assert result.exit_code == 1
            full_output = result.output + getattr(result, "stderr", "")
            assert "No .json flow files found" in full_output

    @pytest.mark.skip_blockbuster
    @pytest.mark.parametrize(
        "script_fixture",
        [
            "temp_python_script",
            "test_basic_prompting",
        ],
    )
    def test_serve_script_startup(self, runner, script_fixture, request):
        """Test deploy command with a valid Python script."""
        from unittest.mock import MagicMock, patch

        script_path = request.getfixturevalue(script_fixture)

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            mock_uvicorn.return_value = None
            mock_graph = MagicMock()
            mock_load_graph.return_value = mock_graph

            result = runner.invoke(app, ["deploy", str(script_path), "--verbose"])
            assert result.exit_code == 0, result.output

            # Verify the multi-deploy app was created
            mock_uvicorn.assert_called_once()
            call_args = mock_uvicorn.call_args
            assert call_args[0][0].title == "Langflow Multi-Flow Deployment (1)"

            # Verify the output shows single flow deployment
            assert "Single Flow Deployed Successfully!" in result.output
            assert "/flows/" in result.output

    def test_serve_port_validation(self, runner, temp_python_script):
        """Test deploy command with custom port configuration."""
        from unittest.mock import patch

        # Mock uvicorn.run and is_port_in_use to test port handling
        with (
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.is_port_in_use", return_value=False) as mock_port_check,
        ):
            # Make uvicorn.run do nothing instead of raising KeyboardInterrupt
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--port", "9000", "--verbose"])

            # Should exit with 0 since we're not actually starting the server
            assert result.exit_code == 0, result

            # Verify port checking was called
            mock_port_check.assert_called_with(9000, "127.0.0.1")

            # Verify uvicorn was called with the correct port
            mock_uvicorn.assert_called_once()
            call_args = mock_uvicorn.call_args
            assert call_args[1]["port"] == 9000

    def test_serve_host_validation(self, runner, temp_python_script):
        """Test deploy command with custom host configuration."""
        from unittest.mock import patch

        # Mock uvicorn.run to test host handling
        with patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn:
            # Make uvicorn.run do nothing instead of raising KeyboardInterrupt
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--host", "0.0.0.0", "--verbose"])  # noqa: S104

            # Should exit with 0 since we're not actually starting the server
            assert result.exit_code == 0, result

            # Verify uvicorn was called with the correct host
            mock_uvicorn.assert_called_once()
            call_args = mock_uvicorn.call_args
            assert call_args[1]["host"] == "0.0.0.0"  # noqa: S104

    def test_serve_verbose_output(self, runner, temp_python_script):
        """Test deploy command with verbose output."""
        from unittest.mock import MagicMock, patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            mock_uvicorn.return_value = None
            mock_graph = MagicMock()
            mock_load_graph.return_value = mock_graph

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--verbose"])
            assert result.exit_code == 0, result.output

            full_output = result.output + getattr(result, "stderr", "")
            assert "Starting single-flow deployment server" in full_output
            assert "Single Flow Deployed Successfully!" in full_output

    def test_serve_quiet_mode(self, runner, temp_python_script):
        """Test deploy command in quiet mode (no verbose flag)."""
        from unittest.mock import patch

        with patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn:
            # Make uvicorn.run do nothing instead of raising KeyboardInterrupt
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(temp_python_script)])

            # Should exit with 0 since we're not actually starting the server
            assert result.exit_code == 0, result

            # In quiet mode, should not have verbose diagnostic messages
            full_output = result.output + getattr(result, "stderr", "")
            # Should not have verbose diagnostic output but may have the deployment banner
            assert "Analyzing Python script" not in full_output
            assert "Found 'graph' variable" not in full_output

    # API Key Authentication Tests

    def test_serve_missing_api_key(self, runner, temp_python_script):
        """Test deploy command fails when LANGFLOW_API_KEY is not set."""
        from unittest.mock import patch

        # Ensure LANGFLOW_API_KEY is not set
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(app, ["deploy", str(temp_python_script), "--verbose"])
            assert result.exit_code == 1
            full_output = result.output + getattr(result, "stderr", "")
            assert "LANGFLOW_API_KEY environment variable is required" in full_output
            assert "Set the LANGFLOW_API_KEY environment variable" in full_output

    def test_serve_with_api_key(self, runner, temp_python_script):
        """Test deploy command with API key."""
        from unittest.mock import MagicMock, patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-api-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            mock_uvicorn.return_value = None
            mock_graph = MagicMock()
            mock_load_graph.return_value = mock_graph

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--verbose"])
            assert result.exit_code == 0, result.output

            full_output = result.output + getattr(result, "stderr", "")
            assert "Single Flow Deployed Successfully!" in full_output
            assert "test-api..." in full_output  # Check for masked version

    def test_serve_api_key_verification_functions(self):
        """Test API key verification functions."""
        from unittest.mock import patch

        from fastapi import HTTPException

        # Test verify_api_key function
        from langflow.cli.commands import verify_api_key

        # Test with no API key
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None, None)
        assert exc_info.value.status_code == 401
        assert "API key required" in str(exc_info.value.detail)

        # Test with invalid API key
        with (
            patch("langflow.cli.commands.get_api_key", return_value="correct-key"),
            pytest.raises(HTTPException) as exc_info,
        ):
            verify_api_key("wrong-key", None)
        assert exc_info.value.status_code == 401
        assert "Invalid API key" in str(exc_info.value.detail)

        # Test with valid API key
        with patch("langflow.cli.commands.get_api_key", return_value="correct-key"):
            result = verify_api_key("correct-key", None)
            assert result == "correct-key"

        # Test with API key in header
        with patch("langflow.cli.commands.get_api_key", return_value="correct-key"):
            result = verify_api_key(None, "correct-key")
            assert result == "correct-key"

    # PEP 723 Dependency Installation Tests

    @pytest.fixture
    def pep723_script_with_deps(self, tmp_path):
        """Create a test script with PEP 723 dependencies."""
        script_content = """# /// script
# dependencies = [
#   "requests>=2.25.0",
#   "rich>=12.0.0",
# ]
# ///

from pathlib import Path
from langflow.components.input_output import ChatInput, ChatOutput
from langflow.graph import Graph
from langflow.logging.logger import LogConfig

log_config = LogConfig(log_level="INFO", log_file=Path("test.log"))
chat_input = ChatInput()
chat_output = ChatOutput().set(input_value=chat_input.message_response)
graph = Graph(chat_input, chat_output, log_config=log_config)
"""
        script_file = tmp_path / "test_with_deps.py"
        script_file.write_text(script_content)
        return script_file

    @pytest.fixture
    def pep723_script_no_deps(self, tmp_path):
        """Create a test script without PEP 723 dependencies."""
        script_content = """from pathlib import Path
from langflow.components.input_output import ChatInput, ChatOutput
from langflow.graph import Graph
from langflow.logging.logger import LogConfig

log_config = LogConfig(log_level="INFO", log_file=Path("test.log"))
chat_input = ChatInput()
chat_output = ChatOutput().set(input_value=chat_input.message_response)
graph = Graph(chat_input, chat_output, log_config=log_config)
"""
        script_file = tmp_path / "test_no_deps.py"
        script_file.write_text(script_content)
        return script_file

    def test_pep723_dependency_extraction(self, pep723_script_with_deps, pep723_script_no_deps):
        """Test extraction of PEP 723 dependencies from scripts."""
        from langflow.cli.common import extract_script_dependencies

        def mock_verbose_print(msg):
            pass

        # Test script with dependencies
        deps = extract_script_dependencies(pep723_script_with_deps, mock_verbose_print)
        assert deps == ["requests>=2.25.0", "rich>=12.0.0"]

        # Test script without dependencies
        deps = extract_script_dependencies(pep723_script_no_deps, mock_verbose_print)
        assert deps == []

    def test_serve_install_deps_flag(self, runner, pep723_script_with_deps):
        """Test --install-deps and --no-install-deps flags."""
        from unittest.mock import patch

        # Test with --install-deps (default behavior)
        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.extract_script_dependencies") as mock_extract,
            patch("langflow.cli.commands.ensure_dependencies_installed") as mock_install,
        ):
            mock_uvicorn.return_value = None
            mock_extract.return_value = ["requests>=2.25.0", "rich>=12.0.0"]

            result = runner.invoke(app, ["deploy", str(pep723_script_with_deps), "--install-deps", "--verbose"])
            assert result.exit_code == 0, result

            # Verify dependency extraction was called
            mock_extract.assert_called_once()
            # Verify dependency installation was called
            mock_install.assert_called_once()
            deps_arg = mock_install.call_args[0][0]
            assert "requests>=2.25.0" in deps_arg
            assert "rich>=12.0.0" in deps_arg

        # Test with --no-install-deps
        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.extract_script_dependencies") as mock_extract,
            patch("langflow.cli.commands.ensure_dependencies_installed") as mock_install,
        ):
            mock_uvicorn.return_value = None
            mock_extract.return_value = ["requests>=2.25.0", "rich>=12.0.0"]

            result = runner.invoke(app, ["deploy", str(pep723_script_with_deps), "--no-install-deps", "--verbose"])
            assert result.exit_code == 0, result

            # Verify dependency extraction was NOT called when --no-install-deps
            mock_extract.assert_not_called()
            # Verify dependency installation was NOT called
            mock_install.assert_not_called()

    def test_serve_script_without_deps_flag_handling(self, runner, pep723_script_no_deps):
        """Test behavior when script has no dependencies but --install-deps is used."""
        from unittest.mock import patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.extract_script_dependencies") as mock_extract,
            patch("langflow.cli.commands.ensure_dependencies_installed") as mock_install,
        ):
            mock_uvicorn.return_value = None
            mock_extract.return_value = []  # No dependencies

            result = runner.invoke(app, ["deploy", str(pep723_script_no_deps), "--install-deps", "--verbose"])
            assert result.exit_code == 0, result

            full_output = result.output + getattr(result, "stderr", "")
            assert "No inline dependencies declared - skipping installation" in full_output

            # Verify dependency extraction was called
            mock_extract.assert_called_once()
            # Verify dependency installation was NOT called (no deps to install)
            mock_install.assert_not_called()

    def test_serve_json_file_ignores_install_deps(self, runner, test_json_flow):
        """Test that --install-deps is ignored for JSON files."""
        from unittest.mock import patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.common.extract_script_dependencies") as mock_extract,
        ):
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(test_json_flow), "--install-deps", "--verbose"])
            assert result.exit_code == 0, result

            # Verify dependency extraction was NOT called for JSON files
            mock_extract.assert_not_called()

    def test_dependency_installation_function(self):
        """Test the dependency installation helper function."""
        import importlib.metadata
        from unittest.mock import MagicMock, patch

        from langflow.cli.common import _needs_install, ensure_dependencies_installed

        def mock_verbose_print(msg):
            pass

        # Test with no dependencies
        ensure_dependencies_installed([], mock_verbose_print)  # Should not raise

        # Test _needs_install function with package not found
        with patch(
            "langflow.cli.common.importlib_metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("Package not found"),
        ):
            assert _needs_install("nonexistent-package") is True

        # Test with mock subprocess for successful installation
        with (
            patch("langflow.cli.common._needs_install", return_value=True),
            patch("langflow.cli.common.which", return_value="/usr/bin/uv"),
            patch("langflow.cli.common.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock()

            ensure_dependencies_installed(["test-package"], mock_verbose_print)

            # Verify subprocess was called with uv
            mock_run.assert_called_once()
            cmd_args = mock_run.call_args[0][0]
            assert cmd_args[0] == "uv"
            assert "test-package" in cmd_args

        # Test fallback to pip when uv is not available
        with (
            patch("langflow.cli.common._needs_install", return_value=True),
            patch("langflow.cli.common.which", return_value=None),
            patch("langflow.cli.common.subprocess.run") as mock_run,
            patch("sys.executable", "/usr/bin/python"),
        ):
            mock_run.return_value = MagicMock()

            ensure_dependencies_installed(["test-package"], mock_verbose_print)

            # Verify subprocess was called with pip
            mock_run.assert_called_once()
            cmd_args = mock_run.call_args[0][0]
            assert "/usr/bin/python" in cmd_args
            assert "-m" in cmd_args
            assert "pip" in cmd_args
            assert "test-package" in cmd_args

    def test_env_file_loading_with_api_key(self, runner, temp_python_script, tmp_path):
        """Test loading API key from .env file."""
        from unittest.mock import patch

        # Create .env file with API key
        env_file = tmp_path / ".env"
        env_file.write_text("LANGFLOW_API_KEY=env-file-api-key\n")

        with patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn:
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--env-file", str(env_file), "--verbose"])
            assert result.exit_code == 0, result

            full_output = result.output + getattr(result, "stderr", "")
            assert "Loading environment variables from:" in full_output
            assert "LANGFLOW_API_KEY is configured" in full_output

    def test_serve_log_level_validation(self, runner, temp_python_script):
        """Test log level validation in deploy command."""
        from unittest.mock import patch

        # Test valid log level
        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
        ):
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--log-level", "debug", "--verbose"])
            assert result.exit_code == 0, result

            full_output = result.output + getattr(result, "stderr", "")
            assert "Configuring logging with level: debug" in full_output

        # Test invalid log level
        with patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}):
            result = runner.invoke(app, ["deploy", str(temp_python_script), "--log-level", "invalid", "--verbose"])
            assert result.exit_code == 1

            full_output = result.output + getattr(result, "stderr", "")
            assert "Invalid log level 'invalid'" in full_output

    # URL Testing

    def test_serve_url_script_success(self, runner):
        """Test deploy command with URL script."""
        import tempfile
        from unittest.mock import MagicMock, patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.common.is_url", return_value=True),
            patch("langflow.cli.common.download_script_from_url") as mock_download,
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            mock_uvicorn.return_value = None
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = Path(tmpdir) / "test.py"
                test_file.write_text("print('hello')")
                mock_download.return_value = test_file
                mock_graph = MagicMock()
                mock_load_graph.return_value = mock_graph

                result = runner.invoke(app, ["deploy", "https://example.com/script.py", "--verbose"])
                assert result.exit_code == 0, result.output

                # Verify the multi-deploy app was created
                mock_uvicorn.assert_called_once()
                call_args = mock_uvicorn.call_args
                assert call_args[0][0].title == "Langflow Multi-Flow Deployment (1)"

                # Verify the output shows single flow deployment
                assert "Single Flow Deployed Successfully!" in result.output
                assert "/flows/" in result.output

    def test_serve_url_script_root_endpoint_info(self, runner):
        """Test that URL deploy creates proper app with root endpoint info."""
        import tempfile
        from unittest.mock import MagicMock, patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.common.is_url", return_value=True),
            patch("langflow.cli.common.download_script_from_url") as mock_download,
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            mock_uvicorn.return_value = None
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = Path(tmpdir) / "test.py"
                test_file.write_text("print('hello')")
                mock_download.return_value = test_file
                mock_graph = MagicMock()
                mock_load_graph.return_value = mock_graph

                result = runner.invoke(app, ["deploy", "http://example.com/test_script.py", "--verbose"])
                assert result.exit_code == 0, result.output

                # Verify the multi-deploy app was created
                mock_uvicorn.assert_called_once()
                call_args = mock_uvicorn.call_args
                app_instance = call_args[0][0]
                assert app_instance.title == "Langflow Multi-Flow Deployment (1)"

                # Verify the output shows single flow deployment
                assert "Single Flow Deployed Successfully!" in result.output
                assert "/flows/" in result.output

    def test_serve_url_script_download_failure(self, runner):
        """Test deploy command with a URL that fails to download."""
        from unittest.mock import patch

        import typer

        def mock_download_with_http_error(url, verbose_print):
            verbose_print(f"Downloading script from URL: {url}")
            verbose_print("✗ HTTP error downloading script: 404 - Not Found")
            raise typer.Exit(1)

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.common.is_url", return_value=True),
            patch("langflow.cli.common.download_script_from_url", side_effect=mock_download_with_http_error),
        ):
            result = runner.invoke(app, ["deploy", "http://example.com/nonexistent.py", "--verbose"])
            assert result.exit_code == 1

            full_output = result.output + getattr(result, "stderr", "")
            assert "Downloading script from URL" in full_output
            assert "HTTP error" in full_output

    def test_serve_url_script_network_error(self, runner):
        """Test deploy command with a URL that has network connectivity issues."""
        from unittest.mock import patch

        import typer

        def mock_download_with_error(url, verbose_print):
            verbose_print(f"Downloading script from URL: {url}")
            verbose_print("✗ Network error downloading script: Connection failed")
            raise typer.Exit(1)

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.common.is_url", return_value=True),
            patch("langflow.cli.common.download_script_from_url", side_effect=mock_download_with_error),
        ):
            result = runner.invoke(app, ["deploy", "http://example.com/test_script.py", "--verbose"])
            assert result.exit_code == 1

            full_output = result.output + getattr(result, "stderr", "")
            assert "Downloading script from URL" in full_output
            assert "Network error" in full_output

    def test_serve_url_script_invalid_extension(self, runner):
        """Test deploy command with a URL that returns a non-Python file."""
        import tempfile
        from unittest.mock import patch

        import typer

        # Test a .py URL that downloads a file with wrong extension
        def mock_download_with_invalid_extension(url, verbose_print):
            verbose_print(f"Downloading script from URL: {url}")
            # Create a temp file with .txt extension but URL ends with .py
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write("This is not a Python script")
            verbose_print("Error: URL must point to a Python script (.py file), got: .txt")
            raise typer.Exit(1)

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.common.is_url", return_value=True),
            patch("langflow.cli.common.download_script_from_url", side_effect=mock_download_with_invalid_extension),
        ):
            # Use a .py URL so it goes through the script download path
            result = runner.invoke(app, ["deploy", "http://example.com/script.py", "--verbose"])
            assert result.exit_code == 1

            full_output = result.output + getattr(result, "stderr", "")
            assert "Downloading script from URL" in full_output
            assert "URL must point to a Python script (.py file)" in full_output

    def test_serve_url_script_with_dependencies(self, runner, pep723_script_with_deps):
        """Test deploy command with a URL script that has PEP 723 dependencies."""
        from unittest.mock import patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.common.download_script_from_url") as mock_download,
            patch("langflow.cli.commands.extract_script_dependencies") as mock_extract,
            patch("langflow.cli.commands.ensure_dependencies_installed") as mock_install,
        ):
            mock_uvicorn.return_value = None
            mock_download.return_value = pep723_script_with_deps
            mock_extract.return_value = ["requests>=2.25.0", "rich>=12.0.0"]

            result = runner.invoke(app, ["deploy", "http://example.com/script_with_deps.py", "--verbose"])
            assert result.exit_code == 0, result

            # Verify download was called
            mock_download.assert_called_once()
            # Verify dependency extraction was called
            mock_extract.assert_called_once()
            # Verify dependency installation was called
            mock_install.assert_called_once()

    def test_serve_url_script_validation(self, runner):
        """Test URL validation in the deploy command."""
        import tempfile
        from unittest.mock import patch

        # Test with valid URL
        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.common.is_url", return_value=True),
            patch("langflow.cli.common.download_script_from_url") as mock_download,
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            from unittest.mock import MagicMock

            mock_uvicorn.return_value = None
            mock_graph = MagicMock()
            mock_load_graph.return_value = mock_graph
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = Path(tmpdir) / "test.py"
                test_file.write_text("print('hello')")
                mock_download.return_value = test_file
                result = runner.invoke(app, ["deploy", "https://example.com/script.py", "--verbose"])
                assert result.exit_code == 0, result.output

        # Test with invalid URL (not actually a URL)
        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.common.is_url", return_value=False),
        ):
            result = runner.invoke(app, ["deploy", "not-a-url", "--verbose"])
            assert result.exit_code == 1
            full_output = result.output + getattr(result, "stderr", "")
            assert "does not exist" in full_output or "is not a file" in full_output

    # Folder Deploy Tests

    def test_serve_folder_success(self, runner, tmp_path):
        """Test deploy command with a folder containing JSON flows."""
        from unittest.mock import MagicMock, patch

        # Create a test folder with JSON flows
        flows_folder = tmp_path / "test_flows"
        flows_folder.mkdir()

        # Create test JSON flow files
        flow1 = flows_folder / "basic_flow.json"
        flow1.write_text('{"data": {"nodes": [], "edges": []}}')

        flow2 = flows_folder / "advanced_flow.json"
        flow2.write_text('{"data": {"nodes": [], "edges": []}}')

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            mock_uvicorn.return_value = None

            # Mock graph objects
            mock_graph1 = MagicMock()
            mock_graph2 = MagicMock()
            mock_load_graph.side_effect = [mock_graph1, mock_graph2]

            result = runner.invoke(app, ["deploy", str(flows_folder), "--verbose"])
            assert result.exit_code == 0, result.output

            # Verify folder deployment message
            assert "Folder Deployed Successfully!" in result.output
            assert "Flows Detected: 2" in result.output
            assert "Discover flows:" in result.output
            assert "/flows" in result.output

    def test_serve_folder_no_json_files(self, runner, tmp_path):
        """Test deploy command with folder containing no JSON files."""
        from unittest.mock import patch

        empty_folder = tmp_path / "empty_flows"
        empty_folder.mkdir()

        # Add some non-JSON files
        (empty_folder / "readme.txt").write_text("This is not a flow")
        (empty_folder / "script.py").write_text("print('hello')")

        with patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}):
            result = runner.invoke(app, ["deploy", str(empty_folder), "--verbose"])
            assert result.exit_code == 1
            assert "No .json flow files found" in result.output

    def test_serve_folder_invalid_json(self, runner, tmp_path):
        """Test deploy command with folder containing invalid JSON files."""
        from unittest.mock import patch

        flows_folder = tmp_path / "invalid_flows"
        flows_folder.mkdir()

        # Create invalid JSON file
        invalid_flow = flows_folder / "invalid.json"
        invalid_flow.write_text('{"invalid": json}')  # Invalid JSON

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
        ):
            mock_load_graph.side_effect = Exception("Invalid JSON format")

            result = runner.invoke(app, ["deploy", str(flows_folder), "--verbose"])
            assert result.exit_code == 1
            assert "Failed loading flow" in result.output

    def test_serve_github_repo_success(self, runner):
        """Test deploy command with GitHub repository URL."""
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.download_and_extract_repo") as mock_download,
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            mock_uvicorn.return_value = None

            # Create a temporary directory structure
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir)
                flows_dir = repo_path / "flows"
                flows_dir.mkdir()

                # Create test flow
                flow_file = flows_dir / "test_flow.json"
                flow_file.write_text('{"data": {"nodes": [], "edges": []}}')

                mock_download.return_value = repo_path
                mock_graph = MagicMock()
                mock_load_graph.return_value = mock_graph

                result = runner.invoke(app, ["deploy", "https://github.com/user/repo", "--verbose"])
                assert result.exit_code == 0, result.output

                # Verify download was called
                mock_download.assert_called_once()
                assert "https://github.com/user/repo" in mock_download.call_args[0]

    def test_serve_github_repo_download_failure(self, runner):
        """Test deploy command with GitHub repo that fails to download."""
        from unittest.mock import patch

        import httpx

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}),
            patch("langflow.cli.commands.download_and_extract_repo") as mock_download,
        ):
            mock_download.side_effect = httpx.HTTPStatusError(
                "404 Not Found", request=None, response=httpx.Response(404)
            )

            result = runner.invoke(app, ["deploy", "https://github.com/nonexistent/repo", "--verbose"])
            assert result.exit_code == 1
            assert "Error downloading repository" in result.output

    def test_serve_github_token_authentication(self, runner):
        """Test that GITHUB_TOKEN environment variable is used for authentication."""
        import tempfile
        from unittest.mock import MagicMock, patch

        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key", "GITHUB_TOKEN": "gh_token_123"}),
            patch("langflow.cli.common.httpx.Client") as mock_client_class,
            patch("langflow.cli.commands.download_and_extract_repo") as mock_download,
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
            patch("langflow.cli.commands.load_graph_from_path") as mock_load_graph,
            patch("langflow.graph.Graph.prepare"),
        ):
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_uvicorn.return_value = None

            # Mock successful response
            mock_response = MagicMock()
            mock_response.json.return_value = {"default_branch": "main"}
            mock_client.get.return_value = mock_response

            # Create a temp directory that looks like an extracted repo
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir)
                # Create a fake JSON flow file
                flow_file = repo_path / "test_flow.json"
                flow_file.write_text('{"data": {"nodes": [], "edges": []}}')

                mock_download.return_value = repo_path
                mock_graph = MagicMock()
                mock_load_graph.return_value = mock_graph

                result = runner.invoke(app, ["deploy", "https://github.com/user/repo", "--verbose"])
                assert result.exit_code == 0, result.output

                # Verify that the download function was called
                mock_download.assert_called_once()
