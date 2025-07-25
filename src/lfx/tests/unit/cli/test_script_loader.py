"""Unit tests for LFX CLI script loader."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lfx.cli.script_loader import (
    _load_module_from_script,
    _validate_graph_instance,
    extract_message_from_result,
    extract_structured_result,
    extract_text_from_result,
    find_graph_variable,
    load_graph_from_script,
    temporary_sys_path,
)


class TestSysPath:
    """Test sys.path manipulation utilities."""

    def test_temporary_sys_path_adds_and_removes(self):
        """Test that temporary_sys_path correctly adds and removes path."""
        test_path = "/test/path"
        original_path = sys.path.copy()

        assert test_path not in sys.path

        with temporary_sys_path(test_path):
            assert test_path in sys.path
            assert sys.path[0] == test_path

        assert test_path not in sys.path
        assert sys.path == original_path

    def test_temporary_sys_path_already_exists(self):
        """Test temporary_sys_path when path already exists."""
        test_path = sys.path[0]  # Use existing path
        original_path = sys.path.copy()

        with temporary_sys_path(test_path):
            # Should not add duplicate
            assert sys.path == original_path

        assert sys.path == original_path

    def test_temporary_sys_path_with_exception(self):
        """Test that path is removed even if exception occurs."""
        test_path = "/test/exception/path"

        def assert_and_raise_exception():
            assert test_path in sys.path
            msg = "Test exception"
            raise ValueError(msg)

        # Test that the path is removed even when an exception occurs
        with pytest.raises(ValueError, match="Test exception"), temporary_sys_path(test_path):
            assert_and_raise_exception()

        assert test_path not in sys.path


class TestModuleLoading:
    """Test module loading functionality."""

    def test_load_module_from_script_success(self):
        """Test successful module loading from script."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("test_var = 'Hello World'\n")
            f.write("def test_func(): return 42\n")
            script_path = Path(f.name)

        try:
            module = _load_module_from_script(script_path)
            assert hasattr(module, "test_var")
            assert module.test_var == "Hello World"
            assert hasattr(module, "test_func")
            assert module.test_func() == 42
        finally:
            script_path.unlink()

    def test_load_module_from_script_import_error(self):
        """Test module loading with import error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import non_existent_module\n")
            script_path = Path(f.name)

        try:
            with pytest.raises(ImportError):
                _load_module_from_script(script_path)
        finally:
            script_path.unlink()

    def test_load_module_from_script_syntax_error(self):
        """Test module loading with syntax error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken_func(\n")  # Invalid syntax
            script_path = Path(f.name)

        try:
            with pytest.raises(SyntaxError):
                _load_module_from_script(script_path)
        finally:
            script_path.unlink()


class TestGraphValidation:
    """Test graph validation functionality."""

    def test_validate_graph_instance_valid(self):
        """Test validation of valid graph instance."""
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph

        # Create a real graph with ChatInput and ChatOutput
        chat_input = ChatInput()
        chat_output = ChatOutput().set(input_value=chat_input.message_response)
        graph = Graph(chat_input, chat_output)

        result = _validate_graph_instance(graph)
        assert result == graph

    def test_validate_graph_instance_wrong_type(self):
        """Test validation with wrong type."""
        not_a_graph = {"not": "a graph"}

        with pytest.raises(TypeError, match="Graph object is not a LFX Graph instance"):
            _validate_graph_instance(not_a_graph)

    def test_validate_graph_instance_missing_chat_input(self):
        """Test validation with missing ChatInput."""
        from lfx.components.input_output import ChatOutput
        from lfx.graph import Graph

        # Create a graph with only ChatOutput, no ChatInput
        chat_output = ChatOutput()
        graph = Graph(start=chat_output, end=chat_output)

        with pytest.raises(ValueError, match="Graph does not contain any ChatInput component"):
            _validate_graph_instance(graph)

    def test_validate_graph_instance_missing_chat_output(self):
        """Test validation with missing ChatOutput."""
        from lfx.components.input_output import ChatInput
        from lfx.graph import Graph

        # Create a graph with only ChatInput, no ChatOutput
        chat_input = ChatInput()
        graph = Graph(start=chat_input, end=chat_input)

        with pytest.raises(ValueError, match="Graph does not contain any ChatOutput component"):
            _validate_graph_instance(graph)


class TestLoadGraphFromScript:
    """Test loading graph from script functionality."""

    def test_load_graph_from_script_success(self):
        """Test successful graph loading from script."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from unittest.mock import MagicMock\n")
            f.write("graph = MagicMock()\n")
            script_path = Path(f.name)

        try:
            mock_graph = MagicMock()
            with patch("lfx.cli.script_loader._validate_graph_instance", return_value=mock_graph) as mock_validate:
                result = load_graph_from_script(script_path)
                assert result == mock_graph
                mock_validate.assert_called_once()
        finally:
            script_path.unlink()

    def test_load_graph_from_script_no_graph_variable(self):
        """Test error when script has no graph variable."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("other_var = 123\n")
            script_path = Path(f.name)

        try:
            with pytest.raises(RuntimeError, match="No 'graph' variable found"):
                load_graph_from_script(script_path)
        finally:
            script_path.unlink()

    def test_load_graph_from_script_import_error(self):
        """Test error handling for import errors."""
        script_path = Path("/non/existent/script.py")

        with pytest.raises(RuntimeError, match="Error executing script"):
            load_graph_from_script(script_path)


class TestResultExtraction:
    """Test result extraction utilities."""

    def test_extract_message_from_result_success(self):
        """Test extracting message from result."""
        mock_message = MagicMock()
        mock_message.model_dump_json.return_value = '{"text": "Hello"}'

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.result_dict.results = {"message": mock_message}

        results = [mock_result]

        message = extract_message_from_result(results)
        assert message == '{"text": "Hello"}'

    def test_extract_message_from_result_no_chat_output(self):
        """Test extraction when no Chat Output found."""
        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Other Component"

        results = [mock_result]

        message = extract_message_from_result(results)
        assert message == "No response generated"

    def test_extract_text_from_result_success(self):
        """Test extracting text content from result."""
        mock_message = MagicMock()
        mock_message.text = "Hello World"

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.result_dict.results = {"message": mock_message}

        results = [mock_result]

        text = extract_text_from_result(results)
        assert text == "Hello World"

    def test_extract_text_from_result_no_text_attribute(self):
        """Test extraction when message has no text attribute."""
        mock_message = "Plain string message"

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.result_dict.results = {"message": mock_message}

        results = [mock_result]

        text = extract_text_from_result(results)
        assert text == "Plain string message"

    def test_extract_structured_result_success(self):
        """Test extracting structured result data."""
        mock_message = MagicMock()
        mock_message.text = "Test message"

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.vertex.id = "vertex-123"
        mock_result.result_dict.results = {"message": mock_message}

        results = [mock_result]

        structured = extract_structured_result(results, extract_text=True)

        assert structured == {
            "result": "Test message",
            "type": "message",
            "component": "Chat Output",
            "component_id": "vertex-123",
            "success": True,
        }

    def test_extract_structured_result_extraction_error(self):
        """Test structured extraction with error."""

        # Create a custom message class that raises AttributeError when text is accessed
        class ErrorMessage:
            @property
            def text(self):
                msg = "No text"
                raise AttributeError(msg)

        mock_message = ErrorMessage()

        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.vertex.id = "vertex-123"
        mock_result.result_dict.results = {"message": mock_message}

        results = [mock_result]

        structured = extract_structured_result(results, extract_text=True)

        assert structured["success"] is True
        # When hasattr fails due to AttributeError, the function uses the message object directly
        # No warning should be generated in this case
        assert "warning" not in structured
        assert structured["result"] == mock_message

    def test_extract_structured_result_no_results(self):
        """Test structured extraction with no results."""
        results = []

        structured = extract_structured_result(results)

        assert structured == {
            "text": "No response generated",
            "type": "error",
            "success": False,
        }


class TestFindGraphVariable:
    """Test AST-based graph variable finding."""

    def test_find_graph_variable_function_call(self):
        """Test finding graph variable with function call."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from lfx import Graph\n")
            f.write("\n")
            f.write("graph = Graph(nodes=[], edges=[])\n")
            script_path = Path(f.name)

        try:
            result = find_graph_variable(script_path)
            assert result is not None
            assert result["type"] == "function_call"
            assert result["function"] == "Graph"
            assert result["line_number"] == 3
            assert "graph = Graph" in result["source_line"]
        finally:
            script_path.unlink()

    def test_find_graph_variable_method_call(self):
        """Test finding graph variable with method call."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from lfx import Graph\n")
            f.write("\n")
            f.write("graph = Graph.from_payload(data)\n")
            script_path = Path(f.name)

        try:
            result = find_graph_variable(script_path)
            assert result is not None
            assert result["type"] == "function_call"
            assert result["function"] == "Graph.from_payload"
            assert result["line_number"] == 3
        finally:
            script_path.unlink()

    def test_find_graph_variable_assignment(self):
        """Test finding graph variable with simple assignment."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("existing_graph = get_graph()\n")
            f.write("graph = existing_graph\n")
            script_path = Path(f.name)

        try:
            result = find_graph_variable(script_path)
            assert result is not None
            assert result["type"] == "assignment"
            assert result["line_number"] == 2
            assert "graph = existing_graph" in result["source_line"]
        finally:
            script_path.unlink()

    def test_find_graph_variable_not_found(self):
        """Test when no graph variable is found."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("other_var = 123\n")
            f.write("another_var = 'test'\n")
            script_path = Path(f.name)

        try:
            result = find_graph_variable(script_path)
            assert result is None
        finally:
            script_path.unlink()

    def test_find_graph_variable_syntax_error(self):
        """Test handling of syntax errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(\n")  # Invalid syntax
            script_path = Path(f.name)

        try:
            with patch("typer.echo") as mock_echo:
                result = find_graph_variable(script_path)
                assert result is None
                mock_echo.assert_called_once()
                assert "Invalid Python syntax" in mock_echo.call_args[0][0]
        finally:
            script_path.unlink()

    def test_find_graph_variable_file_not_found(self):
        """Test handling of missing file."""
        script_path = Path("/non/existent/file.py")

        with patch("typer.echo") as mock_echo:
            result = find_graph_variable(script_path)
            assert result is None
            mock_echo.assert_called_once()
            assert "not found" in mock_echo.call_args[0][0]
