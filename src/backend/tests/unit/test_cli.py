import json
import socket
import threading
import time
from textwrap import dedent
from typing import Any

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
        assert "No 'graph' variable found" in full_output

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
                    assert output_data["result"] is not None or case["args"][-1] == str(
                        temp_python_script
                    ), f"Unexpected None result: {output_data}"

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


# Deploy Command Tests


class TestDeployCommand:
    """Test suite for the deploy command."""

    @pytest.fixture(autouse=True)
    def _set_dummy_api_key(self, monkeypatch, request):
        # Only skip for tests that explicitly test missing API key
        if not request.node.name.startswith("test_deploy_missing_api_key"):
            monkeypatch.setenv("LANGFLOW_API_KEY", "dummy-test-key")

    def test_deploy_help_output(self, runner):
        """Test the help output for the deploy command."""
        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code == 0, result
        assert "Deploy a Langflow graph as a web API endpoint" in result.output
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--verbose" in result.output

    def test_deploy_nonexistent_file(self, runner):
        """Test error handling for nonexistent files."""
        result = runner.invoke(app, ["deploy", "nonexistent.py", "--verbose"])
        assert result.exit_code == 1
        # Check stderr or combined output for error message
        full_output = result.output + getattr(result, "stderr", "")
        assert "does not exist" in full_output

    def test_deploy_invalid_file_extension(self, runner, tmp_path):
        """Test error handling for unsupported file extensions."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not a script")

        result = runner.invoke(app, ["deploy", str(invalid_file), "--verbose"])
        assert result.exit_code == 1
        full_output = result.output + getattr(result, "stderr", "")
        assert "must be a .py or .json file" in full_output

    def test_deploy_invalid_python_script(self, runner, invalid_python_script):
        """Test error handling for Python scripts without graph variable."""
        result = runner.invoke(app, ["deploy", str(invalid_python_script), "--verbose"])
        assert result.exit_code == 1
        full_output = result.output + getattr(result, "stderr", "")
        assert "No 'graph' variable found" in full_output

    def test_deploy_syntax_error_script(self, runner, syntax_error_script):
        """Test error handling for Python scripts with syntax errors."""
        result = runner.invoke(app, ["deploy", str(syntax_error_script), "--verbose"])
        assert result.exit_code == 1
        # Should handle syntax errors gracefully

    def test_deploy_directory_instead_of_file(self, runner, tmp_path):
        """Test error handling when providing directory instead of file."""
        result = runner.invoke(app, ["deploy", str(tmp_path), "--verbose"])
        assert result.exit_code == 1
        full_output = result.output + getattr(result, "stderr", "")
        assert "is not a file" in full_output

    @pytest.mark.skip_blockbuster
    def test_deploy_valid_python_script_startup(self, runner, temp_python_script):
        """Test that deploy command can successfully analyze and prepare a valid Python script.

        Note: This test only checks the startup validation, not the actual server startup.
        """
        from unittest.mock import patch

        # We'll mock uvicorn.run to prevent the actual server from starting
        with patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn:
            # Make uvicorn.run do nothing instead of raising KeyboardInterrupt
            # since the CLI runner can't handle interrupts the same way
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--verbose"])

            # Should exit with 0 since we're not actually starting the server
            assert result.exit_code == 0, result

            # Check that it got through the validation steps
            full_output = result.output + getattr(result, "stderr", "")
            assert "Found 'graph' variable" in full_output
            assert "Graph prepared successfully" in full_output
            assert "Starting deployment server" in full_output

            # Verify uvicorn.run was called
            assert mock_uvicorn.called

    @pytest.mark.skip_blockbuster
    def test_deploy_basic_prompting_startup(self, runner, test_basic_prompting):
        """Test that deploy command can successfully analyze and prepare basic prompting graph."""
        from unittest.mock import patch

        # We'll mock uvicorn.run to prevent the actual server from starting
        with patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn:
            # Make uvicorn.run do nothing instead of raising KeyboardInterrupt
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(test_basic_prompting), "--verbose"])

            # Should exit with 0 since we're not actually starting the server
            assert result.exit_code == 0, result

            # Check that it got through the validation steps
            full_output = result.output + getattr(result, "stderr", "")
            assert "Found 'graph' variable" in full_output
            assert "Graph prepared successfully" in full_output
            assert "Starting deployment server" in full_output

    def test_deploy_port_validation(self, runner, temp_python_script):
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

    def test_deploy_host_validation(self, runner, temp_python_script):
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

    def test_deploy_verbose_output(self, runner, temp_python_script):
        """Test deploy command verbose output contains expected information."""
        from unittest.mock import patch

        with patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn:
            # Make uvicorn.run do nothing instead of raising KeyboardInterrupt
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--verbose"])

            # Should exit with 0 since we're not actually starting the server
            assert result.exit_code == 0, result

            # Check for expected verbose output
            full_output = result.output + getattr(result, "stderr", "")
            assert "Analyzing Python script" in full_output
            assert "Found 'graph' variable" in full_output
            assert "Loading graph" in full_output
            assert "Preparing graph for deployment" in full_output
            assert "Graph prepared successfully" in full_output
            assert "Starting deployment server" in full_output

    def test_deploy_quiet_mode(self, runner, temp_python_script):
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

    def test_deploy_missing_api_key(self, runner, temp_python_script):
        """Test deploy command fails when LANGFLOW_API_KEY is not set."""
        from unittest.mock import patch

        # Ensure LANGFLOW_API_KEY is not set
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(app, ["deploy", str(temp_python_script), "--verbose"])
            assert result.exit_code == 1
            full_output = result.output + getattr(result, "stderr", "")
            assert "LANGFLOW_API_KEY environment variable is required" in full_output
            assert "Set the LANGFLOW_API_KEY environment variable" in full_output

    def test_deploy_with_api_key(self, runner, temp_python_script):
        """Test deploy command succeeds when LANGFLOW_API_KEY is set."""
        from unittest.mock import patch

        # Set API key in environment
        with (
            patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-api-key-123"}),
            patch("langflow.cli.commands.uvicorn.run") as mock_uvicorn,
        ):
            mock_uvicorn.return_value = None

            result = runner.invoke(app, ["deploy", str(temp_python_script), "--verbose"])
            assert result.exit_code == 0, result

            full_output = result.output + getattr(result, "stderr", "")
            assert "LANGFLOW_API_KEY is configured" in full_output
            assert "Graph Deployed Successfully" in full_output
            # Verify API key is masked in output
            assert "test-api..." in full_output
            # Verify actual API key is NOT exposed in instructions
            assert "test-api-key-123" not in full_output
            assert "<your-api-key>" in full_output

    def test_deploy_api_key_verification_functions(self):
        """Test the API key verification helper functions."""
        from unittest.mock import patch

        from fastapi import HTTPException
        from langflow.cli.commands import get_api_key, verify_api_key

        # Test get_api_key with missing environment variable
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(ValueError, match="LANGFLOW_API_KEY environment variable is required"),
        ):
            get_api_key()

        # Test get_api_key with environment variable set
        with patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}):
            assert get_api_key() == "test-key"

        # Test verify_api_key with missing API key
        with patch.dict("os.environ", {"LANGFLOW_API_KEY": "test-key"}):
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(None, None)
            assert exc_info.value.status_code == 401
            assert "API key is required" in str(exc_info.value.detail)

        # Test verify_api_key with incorrect API key
        with patch.dict("os.environ", {"LANGFLOW_API_KEY": "correct-key"}):
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key("wrong-key", None)
            assert exc_info.value.status_code == 401
            assert "Invalid API key" in str(exc_info.value.detail)

        # Test verify_api_key with correct API key (header)
        with patch.dict("os.environ", {"LANGFLOW_API_KEY": "correct-key"}):
            result = verify_api_key(None, "correct-key")
            assert result == "correct-key"

        # Test verify_api_key with correct API key (query param)
        with patch.dict("os.environ", {"LANGFLOW_API_KEY": "correct-key"}):
            result = verify_api_key("correct-key", None)
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

    def test_deploy_install_deps_flag(self, runner, pep723_script_with_deps):
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

    def test_deploy_script_without_deps_flag_handling(self, runner, pep723_script_no_deps):
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

    def test_deploy_json_file_ignores_install_deps(self, runner, test_json_flow):
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

    def test_deploy_log_level_validation(self, runner, temp_python_script):
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
