"""Tests for the MCP server implementation in Langflow CLI."""

from unittest.mock import MagicMock, patch

import pytest
from langflow.cli.mcp_server import (
    FlowInfo,
    FlowInput,
    FlowOutput,
    create_mcp_server,
    run_mcp_server,
)
from pydantic import ValidationError

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


class TestFlowModels:
    """Test the Pydantic models for MCP flow data."""

    def test_flow_input_model(self):
        """Test FlowInput model validation."""
        # Valid input
        flow_input = FlowInput(input_value="test input")
        assert flow_input.input_value == "test input"
        assert flow_input.tweaks is None

        # With tweaks
        flow_input_with_tweaks = FlowInput(
            input_value="test input",
            tweaks={"param1": "value1"}
        )
        assert flow_input_with_tweaks.tweaks == {"param1": "value1"}

    def test_flow_output_model(self):
        """Test FlowOutput model validation."""
        # Success output
        output = FlowOutput(
            result="test result",
            execution_time=1.5
        )
        assert output.result == "test result"
        assert output.execution_time == 1.5
        assert output.error is None

        # Error output
        error_output = FlowOutput(
            result=None,
            error="Test error occurred"
        )
        assert error_output.result is None
        assert error_output.error == "Test error occurred"

    def test_flow_info_model(self):
        """Test FlowInfo model validation."""
        flow_info = FlowInfo(
            id="test_flow",
            title="Test Flow",
            description="A test flow description"
        )
        assert flow_info.id == "test_flow"
        assert flow_info.title == "Test Flow"
        assert flow_info.description == "A test flow description"
        assert flow_info.inputs is None
        assert flow_info.outputs is None


class TestMCPServerCreation:
    """Test MCP server creation functionality."""

    @pytest.fixture
    def mock_graph(self):
        """Create a mock graph object."""
        graph = MagicMock()
        graph.run = MagicMock(return_value="mocked_result")
        return graph

    @pytest.fixture
    def mock_meta(self):
        """Create a mock meta object."""
        meta = MagicMock()
        meta.title = "Test Flow"
        meta.description = "Test flow description"
        return meta

    @pytest.fixture
    def sample_graphs_and_metas(self, mock_graph, mock_meta):
        """Create sample graphs and metas for testing."""
        graphs = {
            "flow1": mock_graph,
            "flow2": mock_graph
        }
        metas = {
            "flow1": mock_meta,
            "flow2": mock_meta
        }
        return graphs, metas

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_create_mcp_server_basic(self, mock_fastmcp, sample_graphs_and_metas):
        """Test basic MCP server creation."""
        graphs, metas = sample_graphs_and_metas
        mock_mcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_mcp_instance

        server = create_mcp_server(
            graphs=graphs,
            metas=metas,
            server_name="Test MCP Server"
        )

        # Verify FastMCP was called with correct name
        mock_fastmcp.assert_called_once_with("Test MCP Server")
        assert server == mock_mcp_instance

        # Verify tools were registered (one for each flow)
        assert mock_mcp_instance.tool.call_count == len(graphs)

        # Verify resources were registered
        assert mock_mcp_instance.resource.call_count >= 3  # At least 3 resources

        # Verify prompts were registered
        assert mock_mcp_instance.prompt.call_count >= 2  # At least 2 prompts

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_create_mcp_server_empty_graphs(self, mock_fastmcp):
        """Test MCP server creation with empty graphs."""
        mock_mcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_mcp_instance

        server = create_mcp_server(
            graphs={},
            metas={},
            server_name="Empty Server"
        )

        # Should still create server but with no tools
        mock_fastmcp.assert_called_once_with("Empty Server")
        assert server == mock_mcp_instance

        # No tools should be registered
        assert mock_mcp_instance.tool.call_count == 0

        # Resources and prompts should still be registered
        assert mock_mcp_instance.resource.call_count >= 3
        assert mock_mcp_instance.prompt.call_count >= 2

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_create_mcp_server_with_root_dir(self, mock_fastmcp, sample_graphs_and_metas, tmp_path):
        """Test MCP server creation with root directory."""
        graphs, metas = sample_graphs_and_metas
        mock_mcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_mcp_instance

        server = create_mcp_server(
            graphs=graphs,
            metas=metas,
            server_name="Test Server",
            root_dir=tmp_path
        )

        assert server == mock_mcp_instance
        mock_fastmcp.assert_called_once_with("Test Server")


class TestMCPServerRuntime:
    """Test MCP server runtime functionality."""

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_run_mcp_server_stdio(self, mock_fastmcp):
        """Test running MCP server with stdio transport."""
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.run = MagicMock()

        run_mcp_server(
            mcp_server=mock_mcp_instance,
            transport="stdio"
        )

        # Should call run() with no arguments for stdio
        mock_mcp_instance.run.assert_called_once_with()

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_run_mcp_server_sse(self, mock_fastmcp):
        """Test running MCP server with SSE transport."""
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.run = MagicMock()

        run_mcp_server(
            mcp_server=mock_mcp_instance,
            transport="sse",
            host="0.0.0.0",
            port=8080
        )

        # Should call run() with transport, host, and port
        mock_mcp_instance.run.assert_called_once_with(
            transport="sse",
            host="0.0.0.0",
            port=8080
        )

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_run_mcp_server_websocket(self, mock_fastmcp):
        """Test running MCP server with websocket transport."""
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.run = MagicMock()

        run_mcp_server(
            mcp_server=mock_mcp_instance,
            transport="websocket",
            host="127.0.0.1",
            port=9000
        )

        # Should call run() with transport, host, and port
        mock_mcp_instance.run.assert_called_once_with(
            transport="websocket",
            host="127.0.0.1",
            port=9000
        )

    def test_run_mcp_server_invalid_transport(self):
        """Test running MCP server with invalid transport."""
        mock_mcp_instance = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            run_mcp_server(
                mcp_server=mock_mcp_instance,
                transport="invalid"
            )

        assert "Unsupported transport: invalid" in str(exc_info.value)
        assert "Use 'stdio', 'sse', or 'websocket'" in str(exc_info.value)


class TestMCPServerIntegration:
    """Test MCP server integration with existing Langflow infrastructure."""

    @pytest.mark.asyncio
    async def test_run_mcp_server_sse_transport(self):
        """Test that MCP server runs with SSE transport."""
        with patch("langflow.cli.mcp_server.get_settings_service") as mock_settings:
            with patch("langflow.cli.mcp_server.asyncio.sleep", side_effect=KeyboardInterrupt):
                mock_settings_instance = MagicMock()
                mock_settings_instance.settings.host = "localhost"
                mock_settings_instance.settings.port = 8000
                mock_settings.return_value = mock_settings_instance

                with pytest.raises(KeyboardInterrupt):
                    await run_mcp_server(transport="sse", host="localhost", port=8000)

                # Verify settings were updated
                assert mock_settings_instance.settings.host == "localhost"
                assert mock_settings_instance.settings.port == 8000

    @pytest.mark.asyncio
    async def test_run_mcp_server_invalid_transport(self):
        """Test that invalid transport raises ValueError."""
        with pytest.raises(ValueError, match="Transport 'invalid' not supported"):
            await run_mcp_server(transport="invalid")

    @pytest.mark.asyncio
    async def test_run_mcp_server_stdio_not_supported(self):
        """Test that stdio transport raises ValueError."""
        with pytest.raises(ValueError, match="Transport 'stdio' not supported"):
            await run_mcp_server(transport="stdio")

    @pytest.mark.asyncio
    async def test_run_mcp_server_websocket_not_supported(self):
        """Test that websocket transport raises ValueError."""
        with pytest.raises(ValueError, match="Transport 'websocket' not supported"):
            await run_mcp_server(transport="websocket")

    @pytest.mark.asyncio
    async def test_run_mcp_server_exception_handling(self):
        """Test that exceptions are properly handled."""
        with patch("langflow.cli.mcp_server.get_settings_service", side_effect=Exception("Test error")):
            with pytest.raises(Exception, match="Test error"):
                await run_mcp_server(transport="sse")

    @pytest.mark.asyncio
    async def test_run_mcp_server_logging(self):
        """Test that proper logging occurs."""
        with patch("langflow.cli.mcp_server.get_settings_service") as mock_settings:
            with patch("langflow.cli.mcp_server.logger") as mock_logger:
                with patch("langflow.cli.mcp_server.asyncio.sleep", side_effect=KeyboardInterrupt):
                    mock_settings_instance = MagicMock()
                    mock_settings.return_value = mock_settings_instance

                    with pytest.raises(KeyboardInterrupt):
                        await run_mcp_server(transport="sse", host="test-host", port=9000)

                    # Verify logging calls
                    mock_logger.info.assert_any_call("Starting Langflow MCP server on test-host:9000 using sse transport")
                    mock_logger.info.assert_any_call("MCP server shutdown requested")

    @pytest.mark.asyncio
    async def test_run_mcp_server_settings_update(self):
        """Test that settings are properly updated."""
        with patch("langflow.cli.mcp_server.get_settings_service") as mock_settings:
            with patch("langflow.cli.mcp_server.asyncio.sleep", side_effect=KeyboardInterrupt):
                mock_settings_instance = MagicMock()
                mock_settings.return_value = mock_settings_instance

                with pytest.raises(KeyboardInterrupt):
                    await run_mcp_server(transport="sse", host="custom-host", port=7000)

                # Verify settings were updated with custom values
                assert mock_settings_instance.settings.host == "custom-host"
                assert mock_settings_instance.settings.port == 7000


class TestMCPServerErrorHandling:
    """Test error handling in MCP server functionality."""

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_create_mcp_server_with_none_meta(self, mock_fastmcp):
        """Test MCP server creation when meta is None."""
        mock_graph = MagicMock()
        mock_mcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_mcp_instance

        graphs = {"test_flow": mock_graph}
        metas = {"test_flow": None}  # None meta

        server = create_mcp_server(
            graphs=graphs,
            metas=metas,
            server_name="None Meta Test"
        )

        # Should handle None meta gracefully
        assert server == mock_mcp_instance
        mock_fastmcp.assert_called_once_with("None Meta Test")

    def test_flow_input_validation_error(self):
        """Test FlowInput validation with invalid data."""
        # Missing required field should raise validation error
        with pytest.raises(ValidationError):
            FlowInput()  # Missing input_value

    def test_flow_output_with_both_result_and_error(self):
        """Test FlowOutput can have both result and error."""
        output = FlowOutput(
            result="partial result",
            error="warning message",
            execution_time=2.0
        )
        assert output.result == "partial result"
        assert output.error == "warning message"
        assert output.execution_time == 2.0

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_mcp_server_missing_graph_attributes(self, mock_fastmcp):
        """Test MCP server creation with graphs missing expected attributes."""
        mock_graph = MagicMock()
        mock_graph.run.side_effect = AttributeError("Graph has no run method")

        mock_mcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_mcp_instance

        graphs = {"broken_flow": mock_graph}
        metas = {"broken_flow": MagicMock()}

        # Should not fail during server creation
        server = create_mcp_server(
            graphs=graphs,
            metas=metas,
            server_name="Broken Graph Test"
        )

        assert server == mock_mcp_instance
