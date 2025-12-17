"""Unit tests for the run.base module.

This module demonstrates different testing approaches:

1. UNIT TESTS (with mocks): Test individual functions in isolation
2. INTEGRATION TESTS (with real components): Test with actual graphs and components
3. ENVIRONMENT-BASED TESTS: Test with real environment variable injection

Strategies to reduce mocking:
- Use real components for simple functionality
- Create test-specific components that are predictable
- Test actual graph execution for critical paths
- Mock only external dependencies (file I/O, network calls, etc.)
"""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from lfx.run.base import RunError, output_error, run_flow


class TestRunError:
    """Tests for the RunError exception class."""

    def test_run_error_with_message_only(self):
        """Test RunError with just a message."""
        error = RunError("Test error message")
        assert str(error) == "Test error message"
        assert error.original_exception is None

    def test_run_error_with_original_exception(self):
        """Test RunError with an original exception."""
        original = ValueError("Original error")
        error = RunError("Wrapper message", original)
        assert str(error) == "Wrapper message"
        assert error.original_exception is original
        assert isinstance(error.original_exception, ValueError)

    def test_run_error_inheritance(self):
        """Test that RunError inherits from Exception."""
        error = RunError("Test")
        assert isinstance(error, Exception)


class TestOutputError:
    """Tests for the output_error helper function."""

    def test_output_error_returns_dict(self):
        """Test that output_error returns a proper dict structure."""
        result = output_error("Test error", verbose=False)
        assert isinstance(result, dict)
        assert result["success"] is False
        assert result["type"] == "error"
        assert result["exception_message"] == "Test error"

    def test_output_error_with_exception(self):
        """Test output_error with an exception provided."""
        exc = ValueError("Value error message")
        result = output_error("Test error", verbose=False, exception=exc)
        assert result["exception_type"] == "ValueError"
        assert result["exception_message"] == "Value error message"

    def test_output_error_verbose_writes_to_stderr(self, capsys):
        """Test that verbose mode writes to stderr."""
        output_error("Test error", verbose=True)
        captured = capsys.readouterr()
        assert "Test error" in captured.err

    def test_output_error_non_verbose_silent(self, capsys):
        """Test that non-verbose mode doesn't write to stderr."""
        output_error("Test error", verbose=False)
        captured = capsys.readouterr()
        assert captured.err == ""


class TestRunFlowInputValidation:
    """Tests for run_flow input source validation."""

    @pytest.mark.asyncio
    async def test_no_input_source_raises_error(self):
        """Test that providing no input source raises RunError."""
        with pytest.raises(RunError) as exc_info:
            await run_flow(
                script_path=None,
                flow_json=None,
                stdin=False,
            )
        assert "No input source provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_input_sources_raises_error(self, tmp_path):
        """Test that providing multiple input sources raises RunError."""
        script = tmp_path / "test.py"
        script.write_text("graph = None")

        with pytest.raises(RunError) as exc_info:
            await run_flow(
                script_path=script,
                flow_json='{"data": {}}',
                stdin=False,
            )
        assert "Multiple input sources provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_script_path_and_stdin_raises_error(self, tmp_path):
        """Test that script_path + stdin raises RunError."""
        script = tmp_path / "test.py"
        script.write_text("graph = None")

        with pytest.raises(RunError) as exc_info:
            await run_flow(
                script_path=script,
                flow_json=None,
                stdin=True,
            )
        assert "Multiple input sources provided" in str(exc_info.value)


class TestRunFlowFileValidation:
    """Tests for run_flow file path validation."""

    @pytest.mark.asyncio
    async def test_nonexistent_file_raises_error(self, tmp_path):
        """Test that a non-existent file raises RunError."""
        nonexistent = tmp_path / "does_not_exist.py"

        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=nonexistent)
        assert "does not exist" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_directory_instead_of_file_raises_error(self, tmp_path):
        """Test that a directory raises RunError."""
        directory = tmp_path / "test_dir"
        directory.mkdir()

        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=directory)
        assert "is not a file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_extension_raises_error(self, tmp_path):
        """Test that an invalid file extension raises RunError."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a script")

        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=txt_file)
        assert "must be a .py or .json file" in str(exc_info.value)


class TestRunFlowJsonInput:
    """Tests for run_flow with flow_json input."""

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises RunError."""
        with pytest.raises(RunError) as exc_info:
            await run_flow(flow_json='{"nodes": [invalid')
        assert "Invalid JSON content" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_valid_json_creates_temp_file_and_loads_graph(self):
        """Test that valid JSON creates a temporary file and loads the graph."""
        valid_json = '{"data": {"nodes": [], "edges": []}}'

        # Mock the load functions to avoid actual execution
        with (
            patch("lfx.load.aload_flow_from_json") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_graph = MagicMock()
            mock_graph.context = {}
            mock_graph.vertices = []
            mock_graph.edges = []
            mock_graph.prepare = MagicMock()

            async def mock_async_start(_inputs):
                yield

            mock_graph.async_start = mock_async_start
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            result = await run_flow(flow_json=valid_json)

            # The function should have loaded from JSON successfully
            mock_load.assert_called_once()
            assert result["success"] is True


class TestRunFlowStdinInput:
    """Tests for run_flow with stdin input."""

    @pytest.mark.asyncio
    async def test_empty_stdin_raises_error(self):
        """Test that empty stdin raises RunError."""
        with patch("sys.stdin", StringIO("")):
            with pytest.raises(RunError) as exc_info:
                await run_flow(stdin=True)
            assert "No content received from stdin" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_stdin_json_raises_error(self):
        """Test that invalid JSON from stdin raises RunError."""
        with patch("sys.stdin", StringIO('{"invalid": json')):
            with pytest.raises(RunError) as exc_info:
                await run_flow(stdin=True)
            assert "Invalid JSON content from stdin" in str(exc_info.value)


class TestRunFlowPythonScript:
    """Tests for run_flow with Python script input."""

    @pytest.fixture
    def valid_script(self, tmp_path):
        """Create a valid Python script with a graph variable."""
        script_content = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph

chat_input = ChatInput()
chat_output = ChatOutput().set(input_value=chat_input.message_response)
graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "valid_script.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.fixture
    def no_graph_script(self, tmp_path):
        """Create a script without a graph variable."""
        script_content = """
from lfx.components.input_output import ChatInput
chat_input = ChatInput()
# No graph variable
"""
        script_path = tmp_path / "no_graph.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.mark.asyncio
    async def test_no_graph_variable_raises_error(self, no_graph_script):
        """Test that a script without graph variable raises RunError."""
        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=no_graph_script)
        assert "No 'graph' variable found" in str(exc_info.value)


class TestRunFlowGlobalVariables:
    """Tests for run_flow global variables injection."""

    @pytest.mark.asyncio
    async def test_global_variables_none_does_not_inject(self, tmp_path):
        """Test that global_variables=None does not inject anything."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path, global_variables=None)

            # Verify request_variables was not set in context
            assert "request_variables" not in mock_graph.context

    @pytest.mark.asyncio
    async def test_global_variables_injected_into_context(self, tmp_path):
        """Test that global variables are injected into graph context."""
        script_content = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph

chat_input = ChatInput()
chat_output = ChatOutput().set(input_value=chat_input.message_response)
graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "test_script.py"
        script_path.write_text(script_content)

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            global_vars = {"API_KEY": "secret123", "DEBUG": "true"}

            await run_flow(
                script_path=script_path,
                global_variables=global_vars,
            )

            # Verify global variables were injected
            assert "request_variables" in mock_graph.context
            assert mock_graph.context["request_variables"]["API_KEY"] == "secret123"
            assert mock_graph.context["request_variables"]["DEBUG"] == "true"


class TestRunFlowOutputFormats:
    """Tests for run_flow output format handling."""

    @pytest.fixture
    def mock_successful_execution(self):
        """Set up mocks for successful graph execution."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs):
            yield

        mock_graph.async_start = mock_async_start
        return mock_graph

    @pytest.mark.asyncio
    async def test_json_format_returns_structured_result(self, tmp_path, mock_successful_execution):
        """Test that JSON format returns structured result with logs."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test output"}

            result = await run_flow(script_path=script_path, output_format="json")

            assert "logs" in result
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_text_format_returns_output_dict(self, tmp_path, mock_successful_execution):
        """Test that text format returns dict with output key."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"result": "test output"}

            result = await run_flow(script_path=script_path, output_format="text")

            assert "output" in result
            assert result["format"] == "text"

    @pytest.mark.asyncio
    async def test_message_format_returns_output_dict(self, tmp_path, mock_successful_execution):
        """Test that message format returns dict with output key."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"result": "test output"}

            result = await run_flow(script_path=script_path, output_format="message")

            assert "output" in result
            assert result["format"] == "message"

    @pytest.mark.asyncio
    async def test_result_format_extracts_text(self, tmp_path, mock_successful_execution):
        """Test that result format uses extract_text_from_result."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_text_from_result") as mock_extract_text,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract_text.return_value = "extracted text"

            result = await run_flow(script_path=script_path, output_format="result")

            assert result["output"] == "extracted text"
            assert result["format"] == "result"


class TestRunFlowTiming:
    """Tests for run_flow timing functionality."""

    @pytest.fixture
    def mock_successful_execution(self):
        """Set up mocks for successful graph execution."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        # Create mock results with vertex info
        mock_result = MagicMock()
        mock_result.vertex = MagicMock()
        mock_result.vertex.display_name = "TestComponent"
        mock_result.vertex.id = "test-id-123"

        async def mock_async_start(_inputs):
            yield mock_result

        mock_graph.async_start = mock_async_start
        return mock_graph

    @pytest.mark.asyncio
    async def test_timing_includes_metadata(self, tmp_path, mock_successful_execution):
        """Test that timing=True includes timing metadata in result."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            result = await run_flow(script_path=script_path, timing=True)

            assert "timing" in result
            assert "load_time" in result["timing"]
            assert "execution_time" in result["timing"]
            assert "total_time" in result["timing"]
            assert "component_timings" in result["timing"]

    @pytest.mark.asyncio
    async def test_timing_false_excludes_metadata(self, tmp_path, mock_successful_execution):
        """Test that timing=False excludes timing metadata."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            result = await run_flow(script_path=script_path, timing=False)

            assert "timing" not in result


class TestRunFlowVerbosity:
    """Tests for run_flow verbosity levels."""

    @pytest.mark.asyncio
    async def test_verbose_false_configures_critical_logging(self, tmp_path):
        """Test that verbose=False configures CRITICAL log level."""
        import sys

        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        # Get the actual module from sys.modules (not the instance exported by __init__.py)
        log_module = sys.modules["lfx.log.logger"]

        with (
            patch.object(log_module, "configure") as mock_configure,
            patch("lfx.run.base.find_graph_variable") as mock_find,
        ):
            mock_find.return_value = None  # This will cause an error, but we check configure was called

            with pytest.raises(RunError):
                await run_flow(script_path=script_path, verbose=False)

            mock_configure.assert_called()
            call_args = mock_configure.call_args
            assert call_args.kwargs.get("log_level") == "CRITICAL"

    @pytest.mark.asyncio
    async def test_verbose_true_configures_info_logging(self, tmp_path):
        """Test that verbose=True configures INFO log level."""
        import sys

        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        log_module = sys.modules["lfx.log.logger"]

        with (
            patch.object(log_module, "configure") as mock_configure,
            patch("lfx.run.base.find_graph_variable") as mock_find,
        ):
            mock_find.return_value = None

            with pytest.raises(RunError):
                await run_flow(script_path=script_path, verbose=True)

            mock_configure.assert_called()
            call_args = mock_configure.call_args
            assert call_args.kwargs.get("log_level") == "INFO"

    @pytest.mark.asyncio
    async def test_verbose_detailed_configures_debug_logging(self, tmp_path):
        """Test that verbose_detailed=True configures DEBUG log level."""
        import sys

        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        log_module = sys.modules["lfx.log.logger"]

        with (
            patch.object(log_module, "configure") as mock_configure,
            patch("lfx.run.base.find_graph_variable") as mock_find,
        ):
            mock_find.return_value = None

            with pytest.raises(RunError):
                await run_flow(script_path=script_path, verbose_detailed=True)

            mock_configure.assert_called()
            call_args = mock_configure.call_args
            assert call_args.kwargs.get("log_level") == "DEBUG"

    @pytest.mark.asyncio
    async def test_verbose_full_configures_debug_logging(self, tmp_path):
        """Test that verbose_full=True configures DEBUG log level."""
        import sys

        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        log_module = sys.modules["lfx.log.logger"]

        with (
            patch.object(log_module, "configure") as mock_configure,
            patch("lfx.run.base.find_graph_variable") as mock_find,
        ):
            mock_find.return_value = None

            with pytest.raises(RunError):
                await run_flow(script_path=script_path, verbose_full=True)

            mock_configure.assert_called()
            call_args = mock_configure.call_args
            assert call_args.kwargs.get("log_level") == "DEBUG"


class TestRunFlowVariableValidation:
    """Tests for run_flow global variable validation."""

    @pytest.fixture
    def mock_graph_with_validation_errors(self):
        """Set up mock graph that triggers validation errors."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()
        return mock_graph

    @pytest.mark.asyncio
    async def test_validation_errors_raise_run_error(self, tmp_path, mock_graph_with_validation_errors):
        """Test that validation errors raise RunError."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph_with_validation_errors
            mock_validate.return_value = ["Missing required variable: API_KEY"]

            with pytest.raises(RunError) as exc_info:
                await run_flow(script_path=script_path, check_variables=True)

            assert "Global variable validation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_variables_false_skips_validation(self, tmp_path):
        """Test that check_variables=False skips validation."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph
            mock_extract.return_value = {"success": True}

            await run_flow(script_path=script_path, check_variables=False)

            # validate_global_variables_for_env should not be called
            mock_validate.assert_not_called()


class TestRunFlowInputValueHandling:
    """Tests for run_flow input value handling."""

    @pytest.mark.asyncio
    async def test_input_value_takes_precedence(self, tmp_path):
        """Test that input_value takes precedence over input_value_option."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
            patch("lfx.run.base.InputValueRequest") as mock_input_request,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True}

            await run_flow(
                script_path=script_path,
                input_value="positional",
                input_value_option="option",
            )

            # InputValueRequest should be called with the positional value
            mock_input_request.assert_called_once_with(input_value="positional")

    @pytest.mark.asyncio
    async def test_input_value_option_used_when_no_positional(self, tmp_path):
        """Test that input_value_option is used when input_value is None."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
            patch("lfx.run.base.InputValueRequest") as mock_input_request,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True}

            await run_flow(
                script_path=script_path,
                input_value=None,
                input_value_option="option_value",
            )

            mock_input_request.assert_called_once_with(input_value="option_value")


class TestRunFlowJsonFileExecution:
    """Tests for run_flow JSON file execution."""

    @pytest.fixture
    def simple_json_flow(self, tmp_path):
        """Create a simple JSON flow file."""
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "ChatInput-1",
                        "type": "ChatInput",
                        "data": {"display_name": "Chat Input"},
                    },
                ],
                "edges": [],
            }
        }
        json_path = tmp_path / "flow.json"
        json_path.write_text(json.dumps(flow_data))
        return json_path

    @pytest.mark.asyncio
    async def test_json_file_calls_aload_flow_from_json(self, simple_json_flow):
        """Test that JSON file uses aload_flow_from_json."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.load.aload_flow_from_json") as mock_load_json,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_load_json.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True}

            await run_flow(script_path=simple_json_flow)

            mock_load_json.assert_called_once()
            call_args = mock_load_json.call_args
            assert call_args[0][0] == simple_json_flow


class TestRunFlowEnvironmentIntegration:
    """Integration tests for run_flow with environment variables and real components."""

    @pytest.fixture
    def simple_env_script(self, tmp_path):
        """Create a simple script that uses environment variables."""
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
env_reader.set(trigger=chat_input.message_response)
chat_output = ChatOutput().set(input_value=env_reader.get_env_value)

graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "env_script.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.mark.asyncio
    async def test_run_flow_with_env_vars_integration(self, simple_env_script):
        """Integration test that uses environment variables with real components."""
        global_vars = {"TEST_VAR": "Hello World"}

        result = await run_flow(
            script_path=simple_env_script,
            global_variables=global_vars,
            verbose=False,
            check_variables=False,  # Skip validation for this test
        )

        assert result["success"] is True
        assert "Value: Hello World" in result["result"]

    @pytest.mark.asyncio
    async def test_run_flow_without_env_vars_integration(self, simple_env_script):
        """Integration test without environment variables."""
        result = await run_flow(
            script_path=simple_env_script,
            global_variables=None,
            verbose=False,
            check_variables=False,  # Skip validation for this test
        )

        assert result["success"] is True
        assert "Value: Not Found" in result["result"]


class TestRunFlowExecutionErrors:
    """Tests for run_flow execution error handling."""

    @pytest.mark.asyncio
    async def test_graph_execution_error_raises_run_error(self, tmp_path):
        """Test that graph execution errors are wrapped in RunError."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def failing_async_start(_inputs):
            msg = "Execution failed"
            raise ValueError(msg)
            yield  # Required to make it an async generator

        mock_graph.async_start = failing_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []

            with pytest.raises(RunError) as exc_info:
                await run_flow(script_path=script_path)

            assert "Failed to execute graph" in str(exc_info.value)
            assert exc_info.value.original_exception is not None

    @pytest.mark.asyncio
    async def test_graph_preparation_error_raises_run_error(self, tmp_path):
        """Test that graph preparation errors are wrapped in RunError."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock(side_effect=RuntimeError("Preparation failed"))

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph

            with pytest.raises(RunError) as exc_info:
                await run_flow(script_path=script_path)

            assert "Failed to prepare graph" in str(exc_info.value)
