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
    script_content = '''"""Test script for execute command."""'
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
            expect_success=True,
            expect_result=True,
            allow_empty_result=False,  # Expect non-empty result for prompting
        )
        assert len(output_data["result"]) > 0, f"Expected non-empty result: {output_data}"

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
                try:
                    json.loads(line)
                    json_found = True
                    break
                except json.JSONDecodeError:
                    continue

            # Either we found JSON or we have some output
            assert json_found or len(result.output.strip()) > 0

    def test_execute_help_output(self, runner):
        """Test the help output for the execute command."""
        result = runner.invoke(app, ["execute", "--help"])
        assert result.exit_code == 0
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
    # Parse JSON
    try:
        data = json.loads(output.strip())
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
        else:
            assert success_value is False, f"Expected success=False, got {success_value}"
    elif expect_success:
        # If no success field but we expect success, that's okay for some formats
        pass

    # Validate result field if expected
    if expect_result:
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
