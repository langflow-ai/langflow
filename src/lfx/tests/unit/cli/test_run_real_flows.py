"""Integration tests for the run command with real flows."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lfx.__main__ import app

runner = CliRunner()


class TestExecuteRealFlows:
    """Test run command with real flow files."""

    @pytest.fixture
    def test_data_dir(self):
        """Get the test data directory."""
        return Path(__file__).parent.parent.parent / "data"

    @pytest.fixture
    def simple_chat_json(self, test_data_dir):
        """Path to the simple chat JSON flow."""
        return test_data_dir / "simple_chat_no_llm.json"

    @pytest.fixture
    def simple_chat_py(self, test_data_dir):
        """Path to the simple chat Python script."""
        return test_data_dir / "simple_chat_no_llm.py"

    def test_run_json_flow_basic(self, simple_chat_json):
        """Test executing a basic JSON flow."""
        result = runner.invoke(
            app,
            ["run", str(simple_chat_json), "Hello from test!"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Parse output - should be valid JSON
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output
        assert "Hello from test!" in output["result"]

    def test_run_json_flow_verbose(self, simple_chat_json):
        """Test executing with verbose output."""
        result = runner.invoke(
            app,
            ["run", "--verbose", str(simple_chat_json), "Test verbose"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Verbose output should contain diagnostic messages
        assert "Analyzing JSON flow" in result.stderr
        assert "Valid JSON flow file detected" in result.stderr
        assert "Loading and executing JSON flow" in result.stderr
        assert "Preparing graph for execution" in result.stderr

        # Even in verbose mode, stdout should have the JSON result
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output
        assert "Test verbose" in output["result"]

    @pytest.mark.parametrize("fmt", ["json", "text", "message", "result"])
    def test_run_json_flow_different_formats(self, simple_chat_json, fmt):
        """Test different output formats."""
        result = runner.invoke(
            app,
            ["run", "-f", fmt, str(simple_chat_json), f"Test {fmt} format"],
        )

        # Should succeed
        assert result.exit_code == 0
        assert len(result.stdout) > 0

        if fmt == "json":
            # Should be valid JSON
            output = json.loads(result.stdout)
            assert output["success"] is True
            assert "result" in output
            assert f"Test {fmt} format" in output["result"]
        else:
            # For other formats, check output contains the message
            assert f"Test {fmt} format" in result.stdout

    def test_run_json_flow_with_stdin(self, simple_chat_json):
        """Test executing JSON flow from stdin."""
        with simple_chat_json.open() as f:
            json_content = f.read()

        result = runner.invoke(
            app,
            ["run", "--stdin", "--input-value", "Hello from stdin!"],
            input=json_content,
        )

        # Should succeed
        assert result.exit_code == 0

        # Parse output
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output
        assert "Hello from stdin!" in output["result"]

    def test_run_json_flow_inline(self, simple_chat_json):
        """Test executing JSON flow passed inline."""
        with simple_chat_json.open() as f:
            json_content = f.read()

        result = runner.invoke(
            app,
            ["run", "--flow-json", json_content, "--input-value", "Hello inline!"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Parse output
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output
        assert "Hello inline!" in output["result"]

    def test_run_python_script(self, simple_chat_py):
        """Test executing a Python script with a graph."""
        # Python script should exist
        assert simple_chat_py.exists()

        result = runner.invoke(
            app,
            ["run", str(simple_chat_py), "Hello from Python!"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Parse output - should be JSON
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output
        assert "Hello from Python!" in output["result"]

    def test_run_no_input_value(self, simple_chat_json):
        """Test executing without input value."""
        result = runner.invoke(
            app,
            ["run", str(simple_chat_json)],
        )

        # Should succeed even without input
        assert result.exit_code == 0

        # Parse output
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output

    def test_run_check_variables(self, simple_chat_json):
        """Test the check-variables functionality."""
        result = runner.invoke(
            app,
            ["run", "--check-variables", str(simple_chat_json), "Test"],
        )

        # Should succeed as simple_chat_no_llm doesn't have global variables
        assert result.exit_code == 0

        # Parse output
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output

    def test_run_no_check_variables(self, simple_chat_json):
        """Test disabling variable checking."""
        result = runner.invoke(
            app,
            ["run", "--no-check-variables", str(simple_chat_json), "Test"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Parse output
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output

    def test_run_error_cases(self):
        """Test various error cases."""
        # No input source
        result = runner.invoke(app, ["execute"])
        assert result.exit_code == 2  # Typer returns 2 for missing required arguments
        # Typer's error message will be different from our custom message

        # Non-existent file
        result = runner.invoke(app, ["run", "does_not_exist.json"])
        assert result.exit_code == 1
        # Without verbose, error should be JSON in stdout
        # Extract the last line which should be the JSON error
        lines = result.stdout.strip().split("\n")
        json_line = lines[-1] if lines else ""
        if json_line:
            error_output = json.loads(json_line)
            assert error_output["success"] is False
            assert "does not exist" in error_output["error"]

        # Invalid file extension
        result = runner.invoke(app, ["run", "test.txt"])
        assert result.exit_code == 1
        # Without verbose, error should be JSON in stdout
        # Extract the last line which should be the JSON error
        lines = result.stdout.strip().split("\n")
        json_line = lines[-1] if lines else ""
        if json_line:
            error_output = json.loads(json_line)
            assert error_output["success"] is False
            # The error could be either "does not exist" or "must be a .py or .json file"
            # depending on whether the file exists
            assert "does not exist" in error_output["error"] or "must be a .py or .json file" in error_output["error"]

        # Multiple input sources
        result = runner.invoke(
            app,
            ["run", "--stdin", "--flow-json", '{"data": {}}', "test"],
        )
        assert result.exit_code == 1
        # Without verbose, error should be JSON in stdout
        lines = result.stdout.strip().split("\n")
        json_line = lines[-1] if lines else ""
        if json_line:
            error_output = json.loads(json_line)
            assert error_output["success"] is False
            assert "Multiple input sources" in error_output["error"]

    def test_run_input_precedence(self, simple_chat_json):
        """Test input value precedence (positional over option)."""
        result = runner.invoke(
            app,
            [
                "run",
                str(simple_chat_json),
                "positional_value",
                "--input-value",
                "option_value",
            ],
        )

        # Should succeed
        assert result.exit_code == 0

        # Parse output and verify positional value was used
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output
        assert "positional_value" in output["result"]
        assert "option_value" not in output["result"]

    def test_run_json_output_format(self, simple_chat_json):
        """Test that JSON output is single-line when not verbose, multi-line when verbose."""
        # Non-verbose mode - should be compact single-line JSON
        result = runner.invoke(
            app,
            ["run", str(simple_chat_json), "Test compact"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Output should be single line (no newlines except at the end)
        assert result.stdout.count("\n") == 1  # Only the trailing newline
        # Should still be valid JSON
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "Test compact" in output["result"]

        # Verbose mode - should be pretty-printed multi-line JSON
        result_verbose = runner.invoke(
            app,
            ["run", "--verbose", str(simple_chat_json), "Test pretty"],
        )

        # Should succeed
        assert result_verbose.exit_code == 0

        # stdout should have pretty-printed JSON (multi-line)
        assert result_verbose.stdout.count("\n") > 1  # Multi-line
        output = json.loads(result_verbose.stdout)
        assert output["success"] is True
        assert "Test pretty" in output["result"]

    def test_run_error_output_verbose(self):
        """Test that errors go to stderr when verbose is true."""
        # Non-existent file with verbose flag
        result = runner.invoke(app, ["run", "--verbose", "does_not_exist.json"])
        assert result.exit_code == 1
        # With verbose, error should be in stderr, not JSON in stdout
        assert "does not exist" in result.stderr
        # stdout should not contain JSON error
        if result.stdout:
            # If there's any stdout, it shouldn't be a JSON error
            try:
                output = json.loads(result.stdout)
                assert output.get("success", True) is not False
            except json.JSONDecodeError:
                # That's fine, it's not JSON
                pass


class TestAsyncFunctionality:
    """Test that async functions are being called correctly."""

    @pytest.fixture
    def test_data_dir(self):
        """Get the test data directory."""
        return Path(__file__).parent.parent.parent / "data"

    @pytest.fixture
    def simple_chat_json(self, test_data_dir):
        """Path to the simple chat JSON flow."""
        return test_data_dir / "simple_chat_no_llm.json"

    def test_async_load_is_used(self, simple_chat_json, monkeypatch):
        """Test that aload_flow_from_json is being used - expects failure in lfx environment."""
        from lfx.load import aload_flow_from_json

        # Track if the async function was called
        async_called = False
        original_aload = aload_flow_from_json

        async def mock_aload(*args, **kwargs):
            nonlocal async_called
            async_called = True
            return await original_aload(*args, **kwargs)

        monkeypatch.setattr("lfx.load.aload_flow_from_json", mock_aload)

        result = runner.invoke(
            app,
            ["run", str(simple_chat_json), "Test async"],
        )

        # Should succeed
        assert result.exit_code == 0
        assert async_called, "aload_flow_from_json should have been called"

        # Parse output
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output

    def test_async_start_is_used(self, simple_chat_json):
        """Test that graph.async_start is being used."""
        # This is harder to test without mocking the entire graph,
        # but we can at least verify the flow completes successfully
        result = runner.invoke(
            app,
            ["run", "--verbose", str(simple_chat_json), "Test async start"],
        )

        # Should succeed
        assert result.exit_code == 0

        # If async_start wasn't working, we'd get an error
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert "result" in output
