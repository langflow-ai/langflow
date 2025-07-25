"""Unit tests for LFX CLI common utilities."""

import os
import socket
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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

            result = load_graph_from_path(path, verbose_print, verbose=True)

            assert result == mock_graph
            verbose_print.assert_any_call(f"Loading flow from: {path}")
            verbose_print.assert_any_call("✓ Successfully loaded flow with 3 nodes")

    def test_load_graph_from_path_failure(self):
        """Test graph loading failure."""
        with patch("lfx.cli.common.load_flow_from_json", side_effect=Exception("Load error")):
            verbose_print = Mock()
            path = Path("/test/flow.json")

            with pytest.raises(typer.Exit) as exc_info:
                load_graph_from_path(path, verbose_print)

            assert exc_info.value.exit_code == 1
            verbose_print.assert_any_call(f"✗ Failed to load flow from {path}: Load error")


class TestGraphExecution:
    """Test graph execution utilities."""

    @pytest.mark.asyncio
    async def test_execute_graph_with_capture_success(self):
        """Test successful graph execution with output capture."""
        # Mock graph and outputs
        mock_output = MagicMock()
        mock_output.outputs = [MagicMock(results={"text": "Test result"})]

        mock_graph = AsyncMock()
        mock_graph.arun.return_value = [mock_output]

        results, logs = await execute_graph_with_capture(mock_graph, "test input")

        assert results == [{"text": "Test result"}]
        assert logs == ""

        # Verify graph was called correctly
        mock_graph.arun.assert_called_once()
        call_args = mock_graph.arun.call_args
        assert call_args.kwargs["stream"] is False
        assert len(call_args.kwargs["inputs"]) == 1
        assert call_args.kwargs["inputs"][0].input_value == "test input"

    @pytest.mark.asyncio
    async def test_execute_graph_with_capture_with_message(self):
        """Test graph execution with message output."""
        # Mock output with message
        mock_message = MagicMock()
        mock_message.text = "Message text"

        mock_out = MagicMock()
        mock_out.message = mock_message
        del mock_out.results  # No results attribute

        mock_output = MagicMock()
        mock_output.outputs = [mock_out]

        mock_graph = AsyncMock()
        mock_graph.arun.return_value = [mock_output]

        results, logs = await execute_graph_with_capture(mock_graph, "test input")

        assert results == [{"text": "Message text"}]

    @pytest.mark.asyncio
    async def test_execute_graph_with_capture_error(self):
        """Test graph execution with error."""
        mock_graph = AsyncMock()
        mock_graph.arun.side_effect = RuntimeError("Execution failed")

        results, logs = await execute_graph_with_capture(mock_graph, "test input")

        assert results == []
        assert "ERROR: Execution failed" in logs


class TestResultExtraction:
    """Test result data extraction."""

    def test_extract_result_data_no_results(self):
        """Test extraction when no results."""
        result = extract_result_data([], "some logs")

        assert result == {
            "result": "No output generated",
            "success": False,
            "type": "error",
            "component": "",
        }

    def test_extract_result_data_dict_result(self):
        """Test extraction with dictionary result."""
        results = [{"text": "Hello world", "component": "ChatOutput"}]

        result = extract_result_data(results, "logs")

        assert result == {
            "result": "Hello world",
            "text": "Hello world",
            "success": True,
            "type": "message",
            "component": "ChatOutput",
        }

    def test_extract_result_data_non_dict_result(self):
        """Test extraction with non-dictionary result."""
        results = ["Simple string result"]

        result = extract_result_data(results, "logs")

        assert result == {
            "result": "Simple string result",
            "text": "Simple string result",
            "success": True,
            "type": "message",
            "component": "",
        }

    def test_extract_result_data_multiple_results(self):
        """Test extraction uses last result when multiple results."""
        results = [
            {"text": "First result"},
            {"text": "Last result", "component": "FinalOutput"},
        ]

        result = extract_result_data(results, "logs")

        assert result["result"] == "Last result"
        assert result["component"] == "FinalOutput"
