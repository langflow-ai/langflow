"""Unit tests for LFX CLI common utilities."""

import os
import socket
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import typer

from lfx.cli.common import (
    create_verbose_printer,
    execute_graph_with_capture,
    extract_result_data,
    flow_id_from_path,
    get_api_key,
    get_best_access_host,
    get_free_port,
    is_port_in_use,
    load_graph_from_path,
)


class TestVerbosePrinter:
    """Test verbose printer functionality."""

    def test_verbose_printer_when_verbose_true(self):
        """Test that verbose printer prints when verbose is True."""
        with patch.object(typer, "echo") as mock_echo:
            printer = create_verbose_printer(verbose=True)
            printer("Test message")
            mock_echo.assert_called_once_with("Test message", file=sys.stderr)

    def test_verbose_printer_when_verbose_false(self):
        """Test that verbose printer doesn't print when verbose is False."""
        with patch.object(typer, "echo") as mock_echo:
            printer = create_verbose_printer(verbose=False)
            printer("Test message")
            mock_echo.assert_not_called()


class TestPortUtilities:
    """Test port-related utilities."""

    def test_is_port_in_use_free_port(self):
        """Test checking if a port is free."""
        # Find a free port first
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            free_port = s.getsockname()[1]

        # Port should be free after closing socket
        assert not is_port_in_use(free_port)

    def test_is_port_in_use_occupied_port(self):
        """Test checking if a port is occupied."""
        # Occupy a port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            occupied_port = s.getsockname()[1]
            # While socket is open, port should be in use
            assert is_port_in_use(occupied_port)

    def test_get_free_port_finds_available_port(self):
        """Test finding a free port."""
        port = get_free_port(8000)
        assert isinstance(port, int)
        assert 8000 <= port <= 65535
        # Verify the port is actually free
        assert not is_port_in_use(port)

    def test_get_free_port_with_occupied_starting_port(self):
        """Test finding a free port when starting port is occupied."""
        # Occupy a port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            occupied_port = s.getsockname()[1]

            # Should find a different port
            free_port = get_free_port(occupied_port)
            assert free_port != occupied_port
            assert not is_port_in_use(free_port)

    def test_get_free_port_no_ports_available(self):
        """Test error when no free ports are available."""
        with patch("socket.socket") as mock_socket:
            # Mock socket to always raise OSError (port in use)
            mock_socket.return_value.__enter__.return_value.bind.side_effect = OSError

            with pytest.raises(RuntimeError, match="No free ports available"):
                get_free_port(65534)  # Start near the end


class TestHostUtilities:
    """Test host-related utilities."""

    @pytest.mark.parametrize(
        ("input_host", "expected"),
        [
            ("0.0.0.0", "localhost"),
            ("", "localhost"),
            ("127.0.0.1", "127.0.0.1"),
            ("localhost", "localhost"),
            ("example.com", "example.com"),
        ],
    )
    def test_get_best_access_host(self, input_host, expected):
        """Test getting the best access host for display."""
        assert get_best_access_host(input_host) == expected


class TestApiKey:
    """Test API key utilities."""

    def test_get_api_key_success(self):
        """Test getting API key when it exists."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):
            assert get_api_key() == "test-api-key"

    def test_get_api_key_not_set(self):
        """Test error when API key is not set."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="LANGFLOW_API_KEY environment variable is not set"),
        ):
            get_api_key()

    def test_get_api_key_empty_string(self):
        """Test error when API key is empty string."""
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": ""}),
            pytest.raises(ValueError, match="LANGFLOW_API_KEY environment variable is not set"),
        ):
            get_api_key()


class TestFlowId:
    """Test flow ID generation."""

    def test_flow_id_from_path_deterministic(self):
        """Test that flow ID generation is deterministic."""
        root = Path("/test/root")
        path = Path("/test/root/flows/example.json")

        # Generate ID multiple times
        id1 = flow_id_from_path(path, root)
        id2 = flow_id_from_path(path, root)

        # Should be the same
        assert id1 == id2
        # Should be a valid UUID
        assert uuid.UUID(id1)

    def test_flow_id_from_path_different_paths(self):
        """Test that different paths generate different IDs."""
        root = Path("/test/root")
        path1 = Path("/test/root/flows/example1.json")
        path2 = Path("/test/root/flows/example2.json")

        id1 = flow_id_from_path(path1, root)
        id2 = flow_id_from_path(path2, root)

        assert id1 != id2


class TestLoadGraph:
    """Test graph loading functionality."""

    def test_load_graph_from_path_success(self):
        """Test successful graph loading from JSON."""
        mock_graph = MagicMock()
        mock_graph.nodes = [1, 2, 3]

        with patch("lfx.cli.common.load_flow_from_json", return_value=mock_graph):
            verbose_print = Mock()
            path = Path("/test/flow.json")

            result = load_graph_from_path(path, ".json", verbose_print, verbose=True)

            assert result == mock_graph
            verbose_print.assert_any_call(f"Analyzing JSON flow: {path}")
            verbose_print.assert_any_call("Loading JSON flow...")

    def test_load_graph_from_path_failure(self):
        """Test graph loading failure."""
        with patch("lfx.cli.common.load_flow_from_json", side_effect=Exception("Load error")):
            verbose_print = Mock()
            path = Path("/test/flow.json")

            with pytest.raises(typer.Exit) as exc_info:
                load_graph_from_path(path, ".json", verbose_print)

            assert exc_info.value.exit_code == 1
            verbose_print.assert_any_call("✗ Failed to load graph: Load error")


class TestGraphExecution:
    """Test graph execution utilities."""

    @pytest.mark.asyncio
    async def test_execute_graph_with_capture_success(self):
        """Test successful graph execution with output capture."""
        # Mock graph and async iterator
        mock_result = MagicMock(results={"text": "Test result"})

        async def mock_async_start(inputs):  # noqa: ARG001
            yield mock_result

        mock_graph = MagicMock()
        mock_graph.async_start = mock_async_start

        results, logs = await execute_graph_with_capture(mock_graph, "test input")

        assert len(results) == 1
        assert results[0].results == {"text": "Test result"}
        assert logs == ""

    @pytest.mark.asyncio
    async def test_execute_graph_with_capture_with_message(self):
        """Test graph execution with message output."""
        # Mock result with message
        mock_result = MagicMock()
        mock_result.message.text = "Message text"
        # Ensure results attribute doesn't exist
        delattr(mock_result, "results")

        async def mock_async_start(inputs):  # noqa: ARG001
            yield mock_result

        mock_graph = MagicMock()
        mock_graph.async_start = mock_async_start

        results, logs = await execute_graph_with_capture(mock_graph, "test input")

        assert len(results) == 1
        assert results[0].message.text == "Message text"

    @pytest.mark.asyncio
    async def test_execute_graph_with_capture_error(self):
        """Test graph execution with error."""

        async def mock_async_start_error(inputs):  # noqa: ARG001
            msg = "Execution failed"
            raise RuntimeError(msg)
            yield  # This line never executes but makes it an async generator

        mock_graph = MagicMock()
        mock_graph.async_start = mock_async_start_error

        with pytest.raises(RuntimeError, match="Execution failed"):
            await execute_graph_with_capture(mock_graph, "test input")


class TestResultExtraction:
    """Test result data extraction."""

    def test_extract_result_data_no_results(self):
        """Test extraction when no results."""
        result = extract_result_data([], "some logs")

        assert result == {
            "text": "No response generated",
            "success": False,
            "type": "error",
            "logs": "some logs",
        }

    def test_extract_result_data_dict_result(self):
        """Test extraction with proper vertex structure."""
        # Create mock result with proper vertex structure
        mock_message = MagicMock()
        mock_message.text = "Hello world"

        mock_vertex = MagicMock()
        mock_vertex.custom_component.display_name = "Chat Output"
        mock_vertex.id = "chat_output_id"

        mock_result = MagicMock()
        mock_result.vertex = mock_vertex
        mock_result.result_dict.results = {"message": mock_message}

        results = [mock_result]

        result = extract_result_data(results, "logs")

        assert result == {
            "result": "Hello world",
            "type": "message",
            "component": "Chat Output",
            "component_id": "chat_output_id",
            "success": True,
            "logs": "logs",
        }

    def test_extract_result_data_non_dict_result(self):
        """Test extraction with non-Chat Output component."""
        # Create mock result with different component type
        mock_vertex = MagicMock()
        mock_vertex.custom_component.display_name = "Text Output"  # Not "Chat Output"
        mock_vertex.id = "text_output_id"

        mock_result = MagicMock()
        mock_result.vertex = mock_vertex

        results = [mock_result]

        result = extract_result_data(results, "logs")

        # Should fall back to default since it's not Chat Output
        assert result == {
            "text": "No response generated",
            "success": False,
            "type": "error",
            "logs": "logs",
        }

    def test_extract_result_data_multiple_results(self):
        """Test extraction finds Chat Output in multiple results."""
        # First result - not Chat Output
        mock_vertex1 = MagicMock()
        mock_vertex1.custom_component.display_name = "Text Input"
        mock_result1 = MagicMock()
        mock_result1.vertex = mock_vertex1

        # Second result - Chat Output
        mock_message = MagicMock()
        mock_message.text = "Final result"

        mock_vertex2 = MagicMock()
        mock_vertex2.custom_component.display_name = "Chat Output"
        mock_vertex2.id = "final_output_id"

        mock_result2 = MagicMock()
        mock_result2.vertex = mock_vertex2
        mock_result2.result_dict.results = {"message": mock_message}

        results = [mock_result1, mock_result2]

        result = extract_result_data(results, "logs")

        # Should find and use the Chat Output result
        assert result == {
            "result": "Final result",
            "type": "message",
            "component": "Chat Output",
            "component_id": "final_output_id",
            "success": True,
            "logs": "logs",
        }
