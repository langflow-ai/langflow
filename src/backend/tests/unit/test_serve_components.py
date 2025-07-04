"""Unit tests for serve command components (FastAPI apps, functions, etc.)."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from langflow.cli.serve_app import (
    FlowMeta,
    RunRequest, 
    RunResponse,
    ErrorResponse,
    create_multi_serve_app,
    create_flow_router,
    _analyze_graph_structure,
    _generate_dynamic_run_description,
)
from langflow.cli.common import (
    flow_id_from_path,
    load_graph_from_path,
    validate_script_path,
)
from langflow.cli.mcp_server import run_mcp_server


class TestFlowMeta:
    """Test FlowMeta data model."""

    def test_flow_meta_creation(self):
        """Test FlowMeta creation with all fields."""
        meta = FlowMeta(
            id="test_flow",
            relative_path="test_flow.json",
            title="Test Flow",
            description="A test flow"
        )
        
        assert meta.id == "test_flow"
        assert meta.relative_path == "test_flow.json"
        assert meta.title == "Test Flow"
        assert meta.description == "A test flow"

    def test_flow_meta_optional_fields(self):
        """Test FlowMeta with optional fields."""
        meta = FlowMeta(
            id="minimal_flow",
            relative_path="minimal.json",
            title="Minimal Flow"
        )
        
        assert meta.id == "minimal_flow"
        assert meta.description is None

    def test_flow_meta_serialization(self):
        """Test FlowMeta JSON serialization."""
        meta = FlowMeta(
            id="test_flow",
            relative_path="test_flow.json",
            title="Test Flow",
            description="A test flow"
        )
        
        data = meta.model_dump()
        assert data["id"] == "test_flow"
        assert data["title"] == "Test Flow"


class TestRunModels:
    """Test request/response models."""

    def test_run_request_creation(self):
        """Test RunRequest creation."""
        request = RunRequest(input_value="test input")
        assert request.input_value == "test input"
        assert request.tweaks == {}

    def test_run_request_with_tweaks(self):
        """Test RunRequest with tweaks."""
        tweaks = {"param1": "value1"}
        request = RunRequest(input_value="test", tweaks=tweaks)
        assert request.tweaks == tweaks

    def test_run_response_creation(self):
        """Test RunResponse creation."""
        response = RunResponse(
            result="test result",
            execution_time=1.5,
            flow_id="test_flow"
        )
        
        assert response.result == "test result"
        assert response.execution_time == 1.5
        assert response.flow_id == "test_flow"
        assert response.success is True

    def test_error_response_creation(self):
        """Test ErrorResponse creation."""
        error = ErrorResponse(error="Something went wrong")
        assert error.error == "Something went wrong"
        assert error.success is False


class TestGraphAnalysis:
    """Test graph analysis functions."""

    def test_analyze_graph_structure_basic(self):
        """Test basic graph structure analysis."""
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        # Mock vertices (nodes)
        mock_vertex1 = MagicMock()
        mock_vertex1.vertex_type = "InputNode"
        mock_vertex1.display_name = "Input"
        
        mock_vertex2 = MagicMock()
        mock_vertex2.vertex_type = "OutputNode"
        mock_vertex2.display_name = "Output"
        
        mock_graph.vertices = [mock_vertex1, mock_vertex2]
        
        result = _analyze_graph_structure(mock_graph)
        
        assert "flow_id" in result
        assert result["flow_id"] == "test_flow"
        assert "total_nodes" in result
        assert result["total_nodes"] == 2
        assert "node_types" in result
        assert "InputNode" in result["node_types"]
        assert "OutputNode" in result["node_types"]

    def test_analyze_graph_structure_empty(self):
        """Test graph analysis with empty graph."""
        mock_graph = MagicMock()
        mock_graph.flow_id = "empty_flow"
        mock_graph.vertices = []
        
        result = _analyze_graph_structure(mock_graph)
        
        assert result["total_nodes"] == 0
        assert result["node_types"] == {}

    def test_generate_dynamic_run_description(self):
        """Test dynamic description generation."""
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        # Mock the analysis function
        with patch("langflow.cli.serve_app._analyze_graph_structure") as mock_analyze:
            mock_analyze.return_value = {
                "flow_id": "test_flow",
                "total_nodes": 3,
                "node_types": {"InputNode": 1, "ProcessorNode": 1, "OutputNode": 1},
                "input_nodes": ["Input"],
                "output_nodes": ["Output"]
            }
            
            description = _generate_dynamic_run_description(mock_graph)
            
            assert "test_flow" in description
            assert "3 components" in description
            assert isinstance(description, str)
            assert len(description) > 50  # Should be a substantial description


class TestCommonFunctions:
    """Test common utility functions."""

    def test_flow_id_from_path_simple(self):
        """Test flow ID generation from simple path."""
        file_path = Path("/root/my_flow.json")
        root_dir = Path("/root")
        
        flow_id = flow_id_from_path(file_path, root_dir)
        assert flow_id == "my_flow"

    def test_flow_id_from_path_nested(self):
        """Test flow ID generation from nested path."""
        file_path = Path("/root/subfolder/nested_flow.json")
        root_dir = Path("/root")
        
        flow_id = flow_id_from_path(file_path, root_dir)
        assert flow_id == "subfolder_nested_flow"

    def test_flow_id_from_path_special_chars(self):
        """Test flow ID generation with special characters."""
        file_path = Path("/root/my-flow (v2).json")
        root_dir = Path("/root")
        
        flow_id = flow_id_from_path(file_path, root_dir)
        # Should sanitize special characters
        assert flow_id == "my_flow_v2_"

    def test_validate_script_path_python(self, tmp_path):
        """Test script path validation for Python files."""
        python_file = tmp_path / "test.py"
        python_file.write_text("# Test script")
        
        def mock_print(msg):
            pass
        
        extension, resolved = validate_script_path(python_file, mock_print)
        assert extension == ".py"
        assert resolved == python_file

    def test_validate_script_path_json(self, tmp_path):
        """Test script path validation for JSON files."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"test": "data"}')
        
        def mock_print(msg):
            pass
        
        extension, resolved = validate_script_path(json_file, mock_print)
        assert extension == ".json"
        assert resolved == json_file

    def test_validate_script_path_invalid_extension(self, tmp_path):
        """Test script path validation with invalid extension."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("invalid")
        
        def mock_print(msg):
            pass
        
        with pytest.raises(ValueError, match="must be a .py or .json file"):
            validate_script_path(invalid_file, mock_print)

    def test_validate_script_path_nonexistent(self):
        """Test script path validation with nonexistent file."""
        nonexistent = Path("/nonexistent/file.py")
        
        def mock_print(msg):
            pass
        
        with pytest.raises(FileNotFoundError):
            validate_script_path(nonexistent, mock_print)


class TestLoadGraphFromPath:
    """Test graph loading functionality."""

    @patch("langflow.cli.common.load_flow_from_file")
    def test_load_graph_from_path_json(self, mock_load_flow):
        """Test loading graph from JSON file."""
        mock_flow = MagicMock()
        mock_graph = MagicMock()
        mock_flow.data = mock_graph
        mock_load_flow.return_value = mock_flow
        
        def mock_print(msg):
            pass
        
        result = load_graph_from_path(
            Path("test.json"), 
            ".json", 
            mock_print, 
            verbose=False
        )
        
        assert result == mock_graph
        mock_load_flow.assert_called_once()

    @patch("langflow.cli.common.exec")
    @patch("langflow.cli.common.spec_from_file_location")
    @patch("langflow.cli.common.module_from_spec")
    def test_load_graph_from_path_python(self, mock_module, mock_spec, mock_exec):
        """Test loading graph from Python file."""
        # Mock module with graph attribute
        mock_loaded_module = MagicMock()
        mock_graph = MagicMock()
        mock_loaded_module.graph = mock_graph
        mock_module.return_value = mock_loaded_module
        
        mock_spec_obj = MagicMock()
        mock_spec_obj.loader = MagicMock()
        mock_spec.return_value = mock_spec_obj
        
        def mock_print(msg):
            pass
        
        result = load_graph_from_path(
            Path("test.py"), 
            ".py", 
            mock_print, 
            verbose=False
        )
        
        assert result == mock_graph

    @patch("langflow.cli.common.exec")
    @patch("langflow.cli.common.spec_from_file_location")
    @patch("langflow.cli.common.module_from_spec")
    def test_load_graph_from_path_python_no_graph(self, mock_module, mock_spec, mock_exec):
        """Test loading Python file without graph variable."""
        # Mock module without graph attribute
        mock_loaded_module = MagicMock()
        delattr(mock_loaded_module, 'graph')  # Ensure no graph attribute
        mock_module.return_value = mock_loaded_module
        
        mock_spec_obj = MagicMock()
        mock_spec_obj.loader = MagicMock()
        mock_spec.return_value = mock_spec_obj
        
        def mock_print(msg):
            pass
        
        with pytest.raises(ValueError, match="No 'graph' variable found"):
            load_graph_from_path(
                Path("test.py"), 
                ".py", 
                mock_print, 
                verbose=False
            )


class TestFastAPIAppCreation:
    """Test FastAPI app creation and functionality."""

    def test_create_multi_serve_app_basic(self):
        """Test basic FastAPI app creation."""
        # Mock graph and metadata
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        graphs = {"test_flow": mock_graph}
        metas = {
            "test_flow": FlowMeta(
                id="test_flow",
                relative_path="test.json",
                title="Test Flow"
            )
        }
        
        def mock_print(msg):
            pass
        
        app = create_multi_serve_app(
            root_dir=Path("/test"),
            graphs=graphs,
            metas=metas,
            verbose_print=mock_print
        )
        
        assert app.title == "Langflow Multi-Flow Deployment (1)"
        assert len(app.routes) > 0  # Should have routes

    def test_create_multi_serve_app_multiple_flows(self):
        """Test FastAPI app with multiple flows."""
        # Mock multiple graphs
        graphs = {}
        metas = {}
        
        for i in range(3):
            flow_id = f"flow_{i}"
            mock_graph = MagicMock()
            mock_graph.flow_id = flow_id
            graphs[flow_id] = mock_graph
            metas[flow_id] = FlowMeta(
                id=flow_id,
                relative_path=f"flow_{i}.json",
                title=f"Flow {i}"
            )
        
        def mock_print(msg):
            pass
        
        app = create_multi_serve_app(
            root_dir=Path("/test"),
            graphs=graphs,
            metas=metas,
            verbose_print=mock_print
        )
        
        assert app.title == "Langflow Multi-Flow Deployment (3)"

    def test_create_multi_serve_app_with_test_client(self):
        """Test FastAPI app endpoints with test client."""
        # Mock graph
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        graphs = {"test_flow": mock_graph}
        metas = {
            "test_flow": FlowMeta(
                id="test_flow",
                relative_path="test.json",
                title="Test Flow",
                description="A test flow"
            )
        }
        
        def mock_print(msg):
            pass
        
        app = create_multi_serve_app(
            root_dir=Path("/test"),
            graphs=graphs,
            metas=metas,
            verbose_print=mock_print
        )
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        
        # Test flows list endpoint
        response = client.get("/flows")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test_flow"
        assert data[0]["title"] == "Test Flow"


class TestFlowRouter:
    """Test individual flow router creation."""

    def test_create_flow_router(self):
        """Test flow router creation."""
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        meta = FlowMeta(
            id="test_flow",
            relative_path="test.json", 
            title="Test Flow"
        )
        
        router = create_flow_router("test_flow", mock_graph, meta)
        
        assert router.prefix == "/flows/test_flow"
        assert len(router.routes) >= 2  # Should have run and info endpoints

    @patch("langflow.cli.serve_app.simple_run_flow")
    def test_flow_router_run_endpoint(self, mock_simple_run):
        """Test flow router run endpoint."""
        # Mock successful flow execution
        mock_result = MagicMock()
        mock_output = MagicMock()
        mock_output.outputs = [MagicMock()]
        mock_output.outputs[0].messages = []
        mock_output.outputs[0].results = {"output": "test result"}
        mock_result.outputs = [mock_output]
        mock_simple_run.return_value = mock_result
        
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        meta = FlowMeta(
            id="test_flow",
            relative_path="test.json",
            title="Test Flow"
        )
        
        router = create_flow_router("test_flow", mock_graph, meta)
        
        # Create a minimal FastAPI app to test the router
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        client = TestClient(test_app)
        
        # Test run endpoint
        response = client.post(
            "/flows/test_flow/run",
            json={"input_value": "test input"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["flow_id"] == "test_flow"

    def test_flow_router_info_endpoint(self):
        """Test flow router info endpoint."""
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        meta = FlowMeta(
            id="test_flow",
            relative_path="test.json",
            title="Test Flow",
            description="A test flow"
        )
        
        router = create_flow_router("test_flow", mock_graph, meta)
        
        # Create a minimal FastAPI app to test the router
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        client = TestClient(test_app)
        
        # Test info endpoint
        response = client.get("/flows/test_flow/info")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_flow"
        assert data["title"] == "Test Flow"
        assert data["description"] == "A test flow"


class TestMCPServerFunctions:
    """Test MCP server functions."""

    @pytest.mark.asyncio
    async def test_run_mcp_server_sse_basic(self):
        """Test basic MCP server execution with SSE transport."""
        with patch("langflow.cli.mcp_server.get_settings_service") as mock_settings:
            with patch("langflow.cli.mcp_server.asyncio.sleep", side_effect=KeyboardInterrupt):
                mock_settings_instance = MagicMock()
                mock_settings.return_value = mock_settings_instance
                
                with pytest.raises(KeyboardInterrupt):
                    await run_mcp_server(transport="sse", host="localhost", port=8000)
                
                # Verify settings were updated
                assert mock_settings_instance.settings.host == "localhost"
                assert mock_settings_instance.settings.port == 8000

    @pytest.mark.asyncio 
    async def test_run_mcp_server_invalid_transport(self):
        """Test MCP server with invalid transport."""
        with pytest.raises(ValueError, match="Transport 'invalid' not supported"):
            await run_mcp_server(transport="invalid")

    @pytest.mark.asyncio
    async def test_run_mcp_server_settings_error(self):
        """Test MCP server with settings service error."""
        with patch("langflow.cli.mcp_server.get_settings_service", side_effect=Exception("Settings error")):
            with pytest.raises(Exception, match="Settings error"):
                await run_mcp_server(transport="sse")


class TestErrorHandling:
    """Test error handling in serve components."""

    @patch("langflow.cli.serve_app.simple_run_flow")
    def test_flow_execution_error_handling(self, mock_simple_run):
        """Test error handling in flow execution."""
        # Mock flow execution error
        mock_simple_run.side_effect = Exception("Flow execution failed")
        
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        meta = FlowMeta(
            id="test_flow",
            relative_path="test.json",
            title="Test Flow"
        )
        
        router = create_flow_router("test_flow", mock_graph, meta)
        
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        client = TestClient(test_app)
        
        # Test run endpoint with error
        response = client.post(
            "/flows/test_flow/run",
            json={"input_value": "test input"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_invalid_json_in_request(self):
        """Test handling of invalid JSON in requests."""
        mock_graph = MagicMock()
        mock_graph.flow_id = "test_flow"
        
        meta = FlowMeta(
            id="test_flow",
            relative_path="test.json",
            title="Test Flow"
        )
        
        router = create_flow_router("test_flow", mock_graph, meta)
        
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        client = TestClient(test_app)
        
        # Test with invalid JSON structure
        response = client.post(
            "/flows/test_flow/run",
            json={}  # Missing required input_value
        )
        
        assert response.status_code == 422  # Validation error


class TestIntegration:
    """Integration tests for serve components."""

    def test_full_app_integration(self):
        """Test full app integration with multiple flows."""
        # Create mock graphs with different behaviors
        graphs = {}
        metas = {}
        
        for i in range(2):
            flow_id = f"flow_{i}"
            mock_graph = MagicMock()
            mock_graph.flow_id = flow_id
            graphs[flow_id] = mock_graph
            metas[flow_id] = FlowMeta(
                id=flow_id,
                relative_path=f"flow_{i}.json",
                title=f"Flow {i}",
                description=f"Test flow number {i}"
            )
        
        def mock_print(msg):
            pass
        
        app = create_multi_serve_app(
            root_dir=Path("/test"),
            graphs=graphs,
            metas=metas,
            verbose_print=mock_print
        )
        
        client = TestClient(app)
        
        # Test flows endpoint
        response = client.get("/flows")
        assert response.status_code == 200
        flows = response.json()
        assert len(flows) == 2
        
        # Test each flow info endpoint
        for i in range(2):
            response = client.get(f"/flows/flow_{i}/info")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == f"flow_{i}"
            assert data["title"] == f"Flow {i}"
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"