"""Tests for the MCP server implementation in Langflow CLI."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from langflow.cli.mcp_server import (
    FlowInfo,
    FlowInput,
    FlowOutput,
    create_mcp_server,
    run_mcp_server,
)

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
    """Integration tests for MCP server functionality."""

    @pytest.fixture
    def mock_graph_with_execution(self):
        """Create a mock graph that simulates execution."""
        graph = MagicMock()
        
        def mock_run(inputs=None, tweaks=None):
            """Mock graph execution."""
            input_value = inputs.get("input_value", "") if inputs else ""
            if "error" in input_value.lower():
                raise ValueError("Simulated execution error")
            return f"Processed: {input_value}"
        
        graph.run = mock_run
        return graph

    @pytest.fixture
    def integration_graphs_and_metas(self, mock_graph_with_execution):
        """Create graphs and metas for integration testing."""
        graphs = {
            "echo_flow": mock_graph_with_execution,
            "processing_flow": mock_graph_with_execution
        }
        
        # Create more realistic metas
        echo_meta = MagicMock()
        echo_meta.title = "Echo Flow"
        echo_meta.description = "Echoes the input back"
        
        processing_meta = MagicMock()
        processing_meta.title = "Processing Flow"
        processing_meta.description = "Processes input data"
        
        metas = {
            "echo_flow": echo_meta,
            "processing_flow": processing_meta
        }
        
        return graphs, metas

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_mcp_server_tool_execution_success(self, mock_fastmcp, integration_graphs_and_metas):
        """Test successful tool execution through MCP server."""
        graphs, metas = integration_graphs_and_metas
        mock_mcp_instance = MagicMock()
        
        # Track registered tools
        registered_tools = []
        
        def mock_tool_decorator(func):
            registered_tools.append(func)
            return func
        
        mock_mcp_instance.tool.side_effect = lambda: mock_tool_decorator
        mock_fastmcp.return_value = mock_mcp_instance

        # Create the server
        server = create_mcp_server(
            graphs=graphs,
            metas=metas,
            server_name="Integration Test Server"
        )

        # Verify tools were registered
        assert len(registered_tools) == len(graphs)

        # Test tool execution (simulate calling one of the registered tools)
        if registered_tools:
            tool_func = registered_tools[0]
            flow_input = FlowInput(input_value="test input")
            
            # Mock the graph execution context
            with patch("time.time", side_effect=[0, 1.5]):  # Mock execution time
                result = tool_func(flow_input)
            
            assert isinstance(result, FlowOutput)
            assert "Processed: test input" in str(result.result)
            assert result.execution_time == 1.5
            assert result.error is None

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_mcp_server_tool_execution_error(self, mock_fastmcp, integration_graphs_and_metas):
        """Test error handling in tool execution."""
        graphs, metas = integration_graphs_and_metas
        mock_mcp_instance = MagicMock()
        
        registered_tools = []
        
        def mock_tool_decorator(func):
            registered_tools.append(func)
            return func
        
        mock_mcp_instance.tool.side_effect = lambda: mock_tool_decorator
        mock_fastmcp.return_value = mock_mcp_instance

        # Create the server
        server = create_mcp_server(
            graphs=graphs,
            metas=metas,
            server_name="Error Test Server"
        )

        # Test error handling
        if registered_tools:
            tool_func = registered_tools[0]
            error_input = FlowInput(input_value="trigger error")
            
            result = tool_func(error_input)
            
            assert isinstance(result, FlowOutput)
            assert result.result is None
            assert "Simulated execution error" in result.error

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_mcp_server_resources(self, mock_fastmcp, integration_graphs_and_metas):
        """Test MCP server resource functionality."""
        graphs, metas = integration_graphs_and_metas
        mock_mcp_instance = MagicMock()
        
        # Track registered resources
        registered_resources = []
        
        def mock_resource_decorator(uri):
            def decorator(func):
                registered_resources.append((uri, func))
                return func
            return decorator
        
        mock_mcp_instance.resource.side_effect = mock_resource_decorator
        mock_fastmcp.return_value = mock_mcp_instance

        # Create the server
        server = create_mcp_server(
            graphs=graphs,
            metas=metas,
            server_name="Resource Test Server"
        )

        # Verify resources were registered
        assert len(registered_resources) >= 3  # flows, info, schema resources

        # Test the flow list resource
        flows_resource = None
        for uri, func in registered_resources:
            if uri == "flow://flows":
                flows_resource = func
                break
        
        assert flows_resource is not None
        
        # Execute the flows resource
        flows_data = flows_resource()
        flows_json = json.loads(flows_data)
        
        assert isinstance(flows_json, list)
        assert len(flows_json) == len(graphs)
        
        # Check flow info structure
        for flow_info in flows_json:
            assert "id" in flow_info
            assert "title" in flow_info
            assert flow_info["id"] in graphs

    @patch("langflow.cli.mcp_server.FastMCP")
    def test_mcp_server_prompts(self, mock_fastmcp, integration_graphs_and_metas):
        """Test MCP server prompt functionality."""
        graphs, metas = integration_graphs_and_metas
        mock_mcp_instance = MagicMock()
        
        # Track registered prompts
        registered_prompts = []
        
        def mock_prompt_decorator(func):
            registered_prompts.append(func)
            return func
        
        mock_mcp_instance.prompt.side_effect = lambda: mock_prompt_decorator
        mock_fastmcp.return_value = mock_mcp_instance

        # Create the server
        server = create_mcp_server(
            graphs=graphs,
            metas=metas,
            server_name="Prompt Test Server"
        )

        # Verify prompts were registered
        assert len(registered_prompts) >= 2  # help and troubleshooting prompts

        # Test prompt execution
        for prompt_func in registered_prompts:
            prompt_result = prompt_func()
            assert isinstance(prompt_result, str)
            assert len(prompt_result) > 0
            # Should contain information about flows or help
            assert any(keyword in prompt_result.lower() for keyword in 
                      ["flow", "mcp", "help", "execute", "troubleshoot"])


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