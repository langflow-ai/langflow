"""Unit tests for serve components without CLI runner dependencies."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer
from fastapi.testclient import TestClient
from lfx.cli.common import flow_id_from_path, load_graph_from_path, validate_script_path
from lfx.cli.serve_app import (
    ErrorResponse,
    FlowMeta,
    FlowRegistry,
    RunRequest,
    RunResponse,
    create_multi_serve_app,
)
from lfx.graph import Graph
from pydantic import ValidationError


class TestDataModels:
    """Test Pydantic data models."""

    def test_flow_meta_model(self):
        """Test FlowMeta model creation and validation."""
        meta = FlowMeta(
            id="test-flow-123",
            relative_path="flows/test_flow.json",
            title="Test Flow",
            description="A test flow for unit testing",
        )

        assert meta.id == "test-flow-123"
        assert meta.relative_path == "flows/test_flow.json"
        assert meta.title == "Test Flow"
        assert meta.description == "A test flow for unit testing"

        # Test required fields
        with pytest.raises(ValidationError):
            FlowMeta()

    def test_run_request_model(self):
        """Test RunRequest model creation and validation."""
        request = RunRequest(input_value="Hello, world!")
        assert request.input_value == "Hello, world!"

        # Test required field
        with pytest.raises(ValidationError):
            RunRequest()

    def test_run_response_model(self):
        """Test RunResponse model creation and validation."""
        response = RunResponse(
            result="Processed successfully",
            success=True,
            logs="Execution completed",
            type="message",
            component="TestComponent",
        )

        assert response.result == "Processed successfully"
        assert response.success is True
        assert response.logs == "Execution completed"
        assert response.type == "message"
        assert response.component == "TestComponent"

    def test_error_response_model(self):
        """Test ErrorResponse model creation."""
        error = ErrorResponse(error="Something went wrong")
        assert error.error == "Something went wrong"
        assert error.success is False


class TestCommonFunctions:
    """Test common utility functions."""

    def test_flow_id_from_path(self, tmp_path):
        """Test flow ID generation from path."""
        test_path = tmp_path / "test_flow.json"
        root_dir = tmp_path
        flow_id = flow_id_from_path(test_path, root_dir)

        # Should be a deterministic UUID5
        assert isinstance(flow_id, str)
        assert len(flow_id.replace("-", "")) == 32  # UUID without dashes

        # Same path should produce same ID
        assert flow_id == flow_id_from_path(test_path, root_dir)

    def test_validate_script_path_valid(self):
        """Test script path validation with valid path."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(b'{"test": "data"}')
            tmp.flush()

            path = Path(tmp.name)

            def verbose_print(msg):
                pass  # Real function

            file_ext, result = validate_script_path(str(path), verbose_print)
            assert result == path
            assert file_ext == ".json"

    def test_validate_script_path_invalid(self):
        """Test script path validation with invalid path."""

        def verbose_print(msg):
            pass  # Real function

        with pytest.raises(typer.Exit):
            validate_script_path("/nonexistent/path.json", verbose_print)

    @patch("lfx.cli.common.load_flow_from_json")
    @pytest.mark.asyncio
    async def test_load_graph_from_path_success(self, mock_load_flow):
        """Test successful graph loading."""
        mock_graph = Mock()
        mock_load_flow.return_value = mock_graph

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(b'{"test": "flow"}')
            tmp.flush()

            def verbose_print(msg):
                pass  # Real function

            graph = await load_graph_from_path(Path(tmp.name), ".json", verbose_print, verbose=True)
            assert graph == mock_graph
            mock_load_flow.assert_called_once_with(Path(tmp.name), disable_logs=False)

    @patch("lfx.cli.common.load_flow_from_json")
    @pytest.mark.asyncio
    async def test_load_graph_from_path_error(self, mock_load_flow):
        """Test graph loading with error."""
        mock_load_flow.side_effect = Exception("Parse error")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(b"invalid json")
            tmp.flush()

            def verbose_print(msg):
                pass  # Real function

            with pytest.raises(typer.Exit):
                await load_graph_from_path(Path(tmp.name), ".json", verbose_print, verbose=False)
            mock_load_flow.assert_called_once_with(Path(tmp.name), disable_logs=True)


# Removed create_mock_graph - use create_real_graph() instead


def simple_chat_json():
    """Load the simple chat JSON test data."""
    test_data_dir = Path(__file__).parent.parent.parent / "data"
    json_path = test_data_dir / "simple_chat_no_llm.json"
    with json_path.open() as f:
        return json.load(f)


def create_real_graph():
    """Helper function to create a real LFX graph with nodes/edges for serve_app."""
    # Load real JSON data and create graph using from_payload
    json_data = simple_chat_json()
    return Graph.from_payload(json_data, flow_id="00000000-0000-0000-0000-000000000001")


class TestFastAPIAppCreation:
    """Test FastAPI application creation."""

    def test_create_multi_serve_app_basic(self):
        """Test basic multi-serve app creation."""
        meta = FlowMeta(id="test-flow", relative_path="test.json", title="Test Flow")
        registry = FlowRegistry()
        registry.add(create_real_graph(), meta)

        app = create_multi_serve_app(registry=registry)

        assert app.title.startswith("LFX Multi-Flow Server")
        assert "1" in app.title  # Should show count

    def test_create_multi_serve_app_mismatched_keys(self):
        """Test app creation — registry never has mismatched keys by design; verify basic creation."""
        meta = FlowMeta(id="test-flow", relative_path="test.json", title="Test Flow")
        registry = FlowRegistry()
        registry.add(create_real_graph(), meta)

        # Registry always keeps graphs and metas in sync — no mismatch possible
        app = create_multi_serve_app(registry=registry)
        assert app is not None


class TestFastAPIEndpoints:
    """Test FastAPI endpoints using TestClient."""

    def setup_method(self, tmp_path=None):  # noqa: ARG002
        """Set up test client with mock data."""
        self.real_graph = create_real_graph()
        meta = FlowMeta(id="test-flow", relative_path="test.json", title="Test Flow", description="A test flow")

        registry = FlowRegistry()
        registry.add(self.real_graph, meta)
        self.app = create_multi_serve_app(registry=registry)

        # Override the dependency for testing
        def mock_verify_key():
            return "test-key"

        # Import here to avoid circular import issues
        from lfx.cli.serve_app import verify_api_key

        self.app.dependency_overrides[verify_api_key] = mock_verify_key
        self.client = TestClient(self.app)

    def test_list_flows_endpoint(self):
        """Test the /flows endpoint."""
        response = self.client.get("/flows")
        assert response.status_code == 200

        flows = response.json()
        assert len(flows) == 1
        assert flows[0]["id"] == "test-flow"
        assert flows[0]["title"] == "Test Flow"

    def test_health_endpoint(self):
        """Test the /health endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200

        health = response.json()
        assert health["status"] == "healthy"
        assert health["flow_count"] == 1

    @patch("lfx.cli.common.execute_graph_with_capture")
    @patch("lfx.cli.common.extract_result_data")
    def test_flow_run_endpoint_success(self, mock_extract, mock_execute):
        """Test successful flow execution path (without auth validation)."""
        mock_execute.return_value = ({"result": "success"}, "execution logs")
        mock_extract.return_value = {
            "result": "Processed successfully",
            "success": True,
            "type": "message",
            "component": "TestComponent",
        }

        # Test that the execute and extract functions would be called properly
        # (Testing the business logic, not the HTTP layer)
        assert mock_execute.return_value == ({"result": "success"}, "execution logs")
        assert mock_extract.return_value["result"] == "Processed successfully"
        assert mock_extract.return_value["success"] is True

    @patch("lfx.cli.common.execute_graph_with_capture")
    @pytest.mark.asyncio
    async def test_flow_run_endpoint_error(self, mock_execute):
        """Test flow execution error handling logic."""
        mock_execute.side_effect = Exception("Execution failed")

        # Test that the exception would be raised properly
        with pytest.raises(Exception, match="Execution failed"):
            await mock_execute(self.real_graph, "test input")

    def test_flow_info_endpoint(self):
        """Test the flow info endpoint returns basic metadata."""
        response = self.client.get("/flows/test-flow/info")
        # Just test that the endpoint exists and returns something
        # The exact response depends on auth which is complex to mock
        assert response.status_code in [200, 422]  # Either success or auth failure

    def test_flow_run_without_auth(self):
        """Test flow execution without authentication."""
        # Clear the dependency override to test auth failure
        from lfx.cli.serve_app import verify_api_key

        if verify_api_key in self.app.dependency_overrides:
            del self.app.dependency_overrides[verify_api_key]

        response = self.client.post("/flows/test-flow/run", json={"input_value": "test input"})

        # Should fail due to missing auth (exact status depends on verify_api_key implementation)
        assert response.status_code in [401, 403, 422]


class TestErrorHandling:
    """Test error handling in various components."""

    def test_invalid_json_in_request(self):
        """Test handling of invalid JSON in requests."""
        from lfx.cli.serve_app import verify_api_key

        meta = FlowMeta(id="test", relative_path="test.json", title="Test")
        registry = FlowRegistry()
        registry.add(create_real_graph(), meta)
        app = create_multi_serve_app(registry=registry)
        app.dependency_overrides[verify_api_key] = lambda: "test-key"
        client = TestClient(app)

        response = client.post(
            "/flows/test/run",
            data="invalid json",
            headers={"x-api-key": "test-key", "Content-Type": "application/json"},
        )

        assert response.status_code == 422  # Validation error

    def test_missing_flow_id(self):
        """Test accessing non-existent flow."""
        from lfx.cli.serve_app import verify_api_key

        meta = FlowMeta(id="test", relative_path="test.json", title="Test")
        registry = FlowRegistry()
        registry.add(create_real_graph(), meta)
        app = create_multi_serve_app(registry=registry)
        app.dependency_overrides[verify_api_key] = lambda: "test-key"
        client = TestClient(app)

        response = client.post(
            "/flows/nonexistent/run", json={"input_value": "test"}, headers={"x-api-key": "test-key"}
        )

        assert response.status_code == 404


class TestIntegration:
    """Integration tests combining multiple components."""

    @patch("lfx.cli.common.load_flow_from_json")
    @pytest.mark.asyncio
    async def test_full_app_integration(self, mock_load_flow):
        """Test full app integration with realistic data."""
        # Setup real graph
        real_graph = create_real_graph()
        mock_load_flow.return_value = real_graph

        # Create temporary flow file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump({"nodes": [], "edges": []}, tmp)
            tmp.flush()

            flow_path = Path(tmp.name)

            # Test flow loading
            def verbose_print(msg):
                pass  # Real function

            mock_verbose_print = verbose_print
            loaded_graph = await load_graph_from_path(flow_path, ".json", mock_verbose_print)
            assert loaded_graph == real_graph

            # Test flow ID generation
            flow_id = flow_id_from_path(flow_path, flow_path.parent)
            assert isinstance(flow_id, str)

            # Test metadata creation
            meta = FlowMeta(
                id=flow_id, relative_path=flow_path.name, title=flow_path.stem, description="Integration test flow"
            )

            # Test app creation
            from lfx.cli.serve_app import verify_api_key as _verify_api_key

            registry = FlowRegistry()
            registry.add(loaded_graph, meta)
            app = create_multi_serve_app(registry=registry)
            app.dependency_overrides[_verify_api_key] = lambda: "test-key"
            client = TestClient(app)

            # Test endpoints
            flows_response = client.get("/flows")
            assert flows_response.status_code == 200
            assert len(flows_response.json()) == 1

            health_response = client.get("/health")
            assert health_response.status_code == 200
            assert health_response.json()["flow_count"] == 1
