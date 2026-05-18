"""Unit tests for LFX CLI FastAPI serve app."""

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from lfx.cli.serve_app import (
    FlowMeta,
    FlowRegistry,
    create_multi_serve_app,
    verify_api_key,
)
from lfx.graph import Graph
from lfx.graph.schema import ResultData
from lfx.interface.components import component_cache
from lfx.schema.message import Message


def _make_settings_service(*, allow_custom_components: bool = False):
    return SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=allow_custom_components,
        )
    )


def _blocked_raw_graph() -> dict:
    return {
        "nodes": [
            {
                "id": "node-1",
                "data": {
                    "id": "node-1",
                    "type": "TotallyCustom",
                    "node": {
                        "display_name": "Blocked Node",
                        "template": {
                            "code": {"value": "print('blocked')"},
                        },
                    },
                },
            }
        ],
        "edges": [],
    }


@pytest.fixture(autouse=True)
def allow_custom_components_by_default(monkeypatch):
    """Keep constructor-level validation aligned with the serve_app test default path."""
    from lfx.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)


class TestFlowRegistry:
    def _make_meta(self, flow_id: str) -> FlowMeta:
        return FlowMeta(id=flow_id, relative_path=f"{flow_id}.json", title=flow_id, description=None)

    def test_add_and_get(self):
        registry = FlowRegistry()
        graph = MagicMock()
        meta = self._make_meta("flow-1")
        registry.add(graph, meta)
        result = registry.get("flow-1")
        assert result is not None
        assert result[0] is graph
        assert result[1] == meta

    def test_get_missing_returns_none(self):
        assert FlowRegistry().get("nonexistent") is None

    def test_list_metas_empty(self):
        assert FlowRegistry().list_metas() == []

    def test_list_metas_multiple(self):
        registry = FlowRegistry()
        graph = MagicMock()
        registry.add(graph, self._make_meta("a"))
        registry.add(graph, self._make_meta("b"))
        ids = {m.id for m in registry.list_metas()}
        assert ids == {"a", "b"}

    def test_duplicate_add_raises_without_overwrite(self):
        registry = FlowRegistry()
        meta = self._make_meta("flow-1")
        registry.add(MagicMock(), meta)
        with pytest.raises(ValueError, match="already registered"):
            registry.add(MagicMock(), meta)

    def test_duplicate_add_replaces_with_overwrite(self):
        registry = FlowRegistry()
        g1, g2 = MagicMock(), MagicMock()
        meta = self._make_meta("flow-1")
        registry.add(g1, meta)
        registry.add(g2, meta, overwrite=True)
        assert registry.get("flow-1")[0] is g2

    def test_len(self):
        registry = FlowRegistry()
        assert len(registry) == 0
        registry.add(MagicMock(), self._make_meta("x"))
        assert len(registry) == 1

    def test_remove_existing(self):
        registry = FlowRegistry()
        meta = self._make_meta("flow-1")
        registry.add(MagicMock(), meta)
        assert registry.remove("flow-1") is True
        assert registry.get("flow-1") is None

    def test_remove_nonexistent(self):
        assert FlowRegistry().remove("ghost") is False


class TestSecurityFunctions:
    """Test security-related functions."""

    def test_verify_api_key_with_query_param(self):
        """Test API key verification with query parameter."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key-123"}):  # pragma: allowlist secret
            result = verify_api_key("test-key-123", None)
            assert result == "test-key-123"

    def test_verify_api_key_with_header_param(self):
        """Test API key verification with header parameter."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key-123"}):  # pragma: allowlist secret
            result = verify_api_key(None, "test-key-123")
            assert result == "test-key-123"

    def test_verify_api_key_header_takes_precedence(self):
        """Test that query parameter is used when both are provided."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key-123"}):  # pragma: allowlist secret
            result = verify_api_key("test-key-123", "wrong-key")
            assert result == "test-key-123"

    def test_verify_api_key_missing(self):
        """Test error when no API key is provided."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None, None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "API key required"

    def test_verify_api_key_invalid(self):
        """Test error when API key is invalid."""
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "correct-key"}):  # pragma: allowlist secret
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key("wrong-key", None)
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid API key"

    def test_verify_api_key_env_not_set(self):
        """Test error when environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key("any-key", None)
            assert exc_info.value.status_code == 500
            assert "LANGFLOW_API_KEY environment variable is not set" in exc_info.value.detail


class TestCreateServeApp:
    """Test FastAPI app creation."""

    @pytest.fixture
    def simple_chat_json(self):
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    @pytest.fixture
    def real_graph(self, simple_chat_json):
        return Graph.from_payload(simple_chat_json, flow_id="00000000-0000-0000-0000-000000000001")

    @pytest.fixture
    def mock_meta(self):
        return FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="A test flow",
        )

    def test_create_multi_serve_app_single_flow(self, real_graph, mock_meta):
        from lfx.cli.serve_app import FlowRegistry

        registry = FlowRegistry()
        registry.add(real_graph, mock_meta)

        app = create_multi_serve_app(registry=registry, verbose_print=Mock())

        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/flows" in routes
        assert "/flows/{flow_id}/run" in routes
        assert "/flows/{flow_id}/info" in routes
        assert "/flows/upload/" in routes

    def test_create_multi_serve_app_multiple_flows(self, real_graph, mock_meta, simple_chat_json):
        from lfx.cli.serve_app import FlowRegistry

        graph2 = Graph.from_payload(simple_chat_json, flow_id="flow-2")
        meta2 = FlowMeta(id="flow-2", relative_path="flow2.json", title="Flow 2", description=None)

        registry = FlowRegistry()
        registry.add(real_graph, mock_meta)
        registry.add(graph2, meta2)

        app = create_multi_serve_app(registry=registry, verbose_print=Mock())

        routes = [route.path for route in app.routes]
        assert "/flows/{flow_id}/run" in routes
        assert "/flows/{flow_id}/info" in routes
        # Single dispatch route covers all flow IDs — no per-flow routes
        assert "/flows/00000000-0000-0000-0000-000000000001/run" not in routes
        assert "/flows/flow-2/run" not in routes


class TestServeAppEndpoints:
    """Test the FastAPI endpoints."""

    @pytest.fixture
    def simple_chat_json(self):
        """Load the simple chat JSON test data."""
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    @pytest.fixture
    def real_graph_with_async(self, simple_chat_json):
        """Create a real graph with async execution capability."""
        # Create graph using from_payload with real test data
        graph = Graph.from_payload(simple_chat_json, flow_id="00000000-0000-0000-0000-000000000001")

        # Store original async_start to restore later if needed
        original_async_start = graph.async_start

        # Mock successful execution with real ResultData
        async def mock_async_start(inputs, **kwargs):  # noqa: ARG001
            # Create real Message and ResultData objects
            message = Message(text="Hello from flow")
            result_data = ResultData(
                results={"message": message},
                component_display_name="Chat Output",
                component_id=graph.vertices[-1].id if graph.vertices else "test-123",
            )

            # Create a mock result that mimics the real structure
            mock_result = MagicMock()
            mock_result.vertex.custom_component.display_name = "Chat Output"
            mock_result.vertex.id = result_data.component_id
            mock_result.result_dict = result_data

            yield mock_result

        graph.async_start = mock_async_start
        graph._original_async_start = original_async_start

        return graph

    @pytest.fixture
    def app_client(self, real_graph_with_async, monkeypatch):
        """Create test client with single flow app."""
        from lfx.services.deps import get_settings_service

        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="A test flow",
        )

        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)

        app = create_multi_serve_app(
            registry=registry,
            verbose_print=Mock(),
        )

        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        # Set up test API key
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            return TestClient(app)

    @pytest.fixture
    def multi_flow_client(self, real_graph_with_async, simple_chat_json, monkeypatch):
        """Create test client with multiple flows."""
        from lfx.services.deps import get_settings_service

        # Create second real graph using the same JSON structure
        graph2 = Graph.from_payload(simple_chat_json, flow_id="flow-2")

        async def mock_async_start2(inputs, **kwargs):  # noqa: ARG001
            # Return empty results for this test
            yield MagicMock(outputs=[])

        graph2.async_start = mock_async_start2

        meta1 = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="First flow",
        )
        meta2 = FlowMeta(
            id="flow-2",
            relative_path="flow2.json",
            title="Flow 2",
            description="Second flow",
        )

        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta1)
        registry.add(graph2, meta2)

        app = create_multi_serve_app(
            registry=registry,
            verbose_print=Mock(),
        )

        monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            return TestClient(app)

    def test_health_endpoint(self, app_client):
        """Test health check endpoint."""
        response = app_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["flow_count"] == 1

    def test_run_endpoint_success(self, app_client):
        """Test successful flow execution."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.common.extract_structured_result") as mock_extract,
        ):
            mock_extract.return_value = {
                "result": "Hello from flow",
                "success": True,
                "type": "message",
                "component": "TestComponent",
            }
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "Hello from flow"
        assert data["success"] is True
        assert data["type"] == "message"

    def test_run_endpoint_no_auth(self, app_client):
        """Test flow execution without authentication."""
        request_data = {"input_value": "Test input"}

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = app_client.post("/flows/00000000-0000-0000-0000-000000000001/run", json=request_data)

        assert response.status_code == 401
        assert response.json()["detail"] == "API key required"

    def test_run_endpoint_wrong_auth(self, app_client):
        """Test flow execution with wrong API key."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "wrong-key"}

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API key"

    def test_run_endpoint_blocks_custom_components_when_disabled(
        self,
        real_graph_with_async,
    ):
        """Test that /run fails closed before execution when custom components are blocked."""
        real_graph_with_async.raw_graph_data = _blocked_raw_graph()
        meta = FlowMeta(
            id="00000000-0000-0000-0000-000000000001",
            relative_path="test.json",
            title="Test Flow",
            description="A test flow",
        )
        registry = FlowRegistry()
        registry.add(real_graph_with_async, meta)
        app = create_multi_serve_app(
            registry=registry,
            verbose_print=Mock(),
        )
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch(
                "lfx.services.deps.get_settings_service",
                return_value=_make_settings_service(allow_custom_components=False),
            ),
            patch(
                "lfx.utils.flow_validation.ensure_component_hash_lookups_loaded",
                new=AsyncMock(return_value={"ChatInput": {hashlib.sha256(b"known").hexdigest()[:12]}}),
            ),
            patch.object(
                component_cache,
                "type_to_current_hash",
                {"ChatInput": {hashlib.sha256(b"known").hexdigest()[:12]}},
            ),
            patch(
                "lfx.cli.serve_app.execute_graph_with_capture",
                new=AsyncMock(return_value=([], "")),
            ) as mock_execute,
        ):
            client = TestClient(app)
            response = client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run",
                json={"input_value": "Test input"},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "custom components are not allowed" in response.json()["result"]
        mock_execute.assert_not_called()

    def test_run_endpoint_query_auth(self, app_client):
        """Test flow execution with query parameter authentication."""
        request_data = {"input_value": "Test input"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.common.extract_structured_result") as mock_extract,
        ):
            mock_extract.return_value = {
                "result": "Hello from flow",
                "success": True,
                "type": "message",
                "component": "TestComponent",
            }
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run?x-api-key=test-api-key", json=request_data
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_run_endpoint_execution_error(self, app_client):
        """Test flow execution with error."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        # Mock execute_graph_with_capture to raise an error
        async def mock_execute_error(graph, input_value, session_id=None):  # noqa: ARG001
            msg = "Flow execution failed"
            raise RuntimeError(msg)

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_error),
        ):
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200  # Returns 200 with error in response body
        data = response.json()
        assert data["success"] is False
        # serve_app error handling returns "Flow execution failed: {error}"
        assert data["result"] == "Flow execution failed: Flow execution failed"
        assert data["type"] == "error"
        # The error message should be in the logs
        assert "ERROR: Flow execution failed" in data["logs"]

    def test_run_endpoint_no_results(self, app_client):
        """Test flow execution with no results."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        # Mock execute_graph_with_capture to return empty results
        async def mock_execute_empty(graph, input_value, session_id=None):  # noqa: ARG001
            return [], ""  # Empty results and logs

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_empty),
        ):
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "No response generated"
        assert data["success"] is False
        assert data["type"] == "error"

    def test_run_endpoint_forwards_session_id(self, app_client):
        """The /run endpoint must forward session_id from RunRequest to the executor."""
        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["session_id"] = session_id
            return [], ""

        request_data = {"input_value": "Test input", "session_id": "my-conversation"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
        ):
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200
        assert captured["session_id"] == "my-conversation"

    def test_stream_endpoint_forwards_session_id(self, app_client):
        """The /stream endpoint must forward session_id from StreamRequest to the executor."""
        captured: dict = {}

        async def mock_execute_capture(graph, input_value, session_id=None):  # noqa: ARG001
            captured["session_id"] = session_id
            return [], ""

        request_data = {"input_value": "Test input", "session_id": "my-stream-conversation"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute_capture),
            # Drain the streaming response so the background task completes before we assert.
            app_client.stream(
                "POST", "/flows/00000000-0000-0000-0000-000000000001/stream", json=request_data, headers=headers
            ) as response,
        ):
            assert response.status_code == 200
            for _ in response.iter_bytes():
                pass

        assert captured["session_id"] == "my-stream-conversation"

    def test_list_flows_endpoint(self, multi_flow_client):
        """Test listing flows in multi-flow mode."""
        response = multi_flow_client.get("/flows")

        assert response.status_code == 200
        flows = response.json()
        assert len(flows) == 2
        assert any(f["id"] == "00000000-0000-0000-0000-000000000001" for f in flows)
        assert any(f["id"] == "flow-2" for f in flows)

    def test_flow_info_endpoint(self, multi_flow_client):
        """Test getting flow info in multi-flow mode."""
        headers = {"x-api-key": "test-api-key"}

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = multi_flow_client.get("/flows/00000000-0000-0000-0000-000000000001/info", headers=headers)

        assert response.status_code == 200
        info = response.json()
        assert info["id"] == "00000000-0000-0000-0000-000000000001"
        assert info["title"] == "Test Flow"
        assert info["description"] == "First flow"

    def test_flow_run_endpoint_multi_flow(self, multi_flow_client):
        """Test running specific flow in multi-flow mode."""
        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.common.extract_structured_result") as mock_extract,
        ):
            mock_extract.return_value = {
                "result": "Hello from flow",
                "success": True,
                "type": "message",
                "component": "TestComponent",
            }
            response = multi_flow_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "Hello from flow"
        assert data["success"] is True

    def test_invalid_request_body(self, app_client):
        """Test with invalid request body."""
        headers = {"x-api-key": "test-api-key"}

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
            response = app_client.post("/flows/00000000-0000-0000-0000-000000000001/run", json={}, headers=headers)

        assert response.status_code == 422  # Validation error

    def test_flow_execution_with_message_output(self, app_client, real_graph_with_async):
        """Test flow execution with message-type output."""

        # Create a real message output scenario
        async def mock_async_start_message(inputs, **kwargs):  # noqa: ARG001
            # Create real Message and ResultData objects
            message = Message(text="Message output")
            result_data = ResultData(
                results={"message": message}, component_display_name="Chat Output", component_id="test-123"
            )

            # Create result structure
            mock_result = MagicMock()
            mock_result.vertex.custom_component.display_name = "Chat Output"
            mock_result.vertex.id = "test-123"
            mock_result.result_dict = result_data
            # Add message attribute for backwards compatibility
            mock_result.message = message

            yield mock_result

        real_graph_with_async.async_start = mock_async_start_message

        request_data = {"input_value": "Test input"}
        headers = {"x-api-key": "test-api-key"}

        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
            patch("lfx.cli.common.extract_structured_result") as mock_extract,
        ):
            mock_extract.return_value = {
                "result": "Message output",
                "success": True,
                "type": "message",
                "component": "Chat Output",
            }
            response = app_client.post(
                "/flows/00000000-0000-0000-0000-000000000001/run", json=request_data, headers=headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "Message output"
        assert data["success"] is True


class TestUploadEndpoint:
    """Tests for POST /flows/upload/."""

    @pytest.fixture
    def app_with_empty_registry(self):
        from lfx.cli.serve_app import FlowRegistry

        registry = FlowRegistry()
        app = create_multi_serve_app(registry=registry, verbose_print=lambda x: None)  # noqa: ARG005
        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
            yield TestClient(app)

    @pytest.fixture
    def valid_flow_data(self):
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    @pytest.fixture
    def full_export(self):
        """Full Langflow export JSON as exported from the UI (name/data/... at top level).

        This is what a user sends when they run:
            curl -X POST .../flows/upload/ -d @myflow.json

        body.data will be {"edges": [...], "nodes": [...]} — the inner graph with NO
        nested "data" key. A regression that calls load_flow_from_json(body.data)
        raises KeyError('data') here; the correct call passes body.model_dump(...).
        """
        test_data_dir = Path(__file__).parent.parent.parent / "data"
        json_path = test_data_dir / "simple_chat_no_llm.json"
        with json_path.open() as f:
            return json.load(f)

    def test_upload_full_export_as_body(self, app_with_empty_registry, full_export):
        """Uploading a Langflow export JSON directly as the body must succeed.

        Regression test: load_flow_from_json must be called with the full model dict
        (which has a top-level "data" key), not body.data alone (which is just the
        inner graph and has no "data" key).
        """
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json=full_export,
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["name"] == full_export["name"]
        assert body["run_url"].startswith("/flows/")
        assert body["run_url"].endswith("/run")

    def test_upload_valid_flow(self, app_with_empty_registry, valid_flow_data):
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "My Uploaded Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "My Uploaded Flow"
        assert body["run_url"].startswith("/flows/")
        assert body["run_url"].endswith("/run")
        assert "id" in body

    def test_upload_requires_auth(self, app_with_empty_registry, valid_flow_data):
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data},
        )
        assert response.status_code == 401

    def test_upload_invalid_flow_data_returns_422(self, app_with_empty_registry):
        with patch("lfx.cli.serve_app.load_flow_from_json", side_effect=ValueError("bad flow")):
            response = app_with_empty_registry.post(
                "/flows/upload/",
                json={"name": "Bad Flow", "data": {"nodes": [], "edges": []}},
                headers={"x-api-key": "test-key"},
            )
        assert response.status_code == 422
        assert "bad flow" in response.json()["detail"]

    def test_upload_prepare_failure_returns_422(self, app_with_empty_registry):
        mock_graph = MagicMock()
        mock_graph.prepare.side_effect = RuntimeError("prepare failed")
        with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
            response = app_with_empty_registry.post(
                "/flows/upload/",
                json={"name": "Bad Flow", "data": {"nodes": [], "edges": []}},
                headers={"x-api-key": "test-key"},
            )
        assert response.status_code == 422
        assert "prepare failed" in response.json()["detail"]

    def test_upload_flow_is_immediately_listed(self, app_with_empty_registry, valid_flow_data):
        upload_resp = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Runnable Flow", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert upload_resp.status_code == 201
        flow_id = upload_resp.json()["id"]

        list_resp = app_with_empty_registry.get("/flows")
        assert any(f["id"] == flow_id for f in list_resp.json())

    def test_upload_duplicate_without_replace_returns_409(self, app_with_empty_registry, valid_flow_data):
        r1 = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow A", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert r1.status_code == 201

        r2 = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow B", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert r2.status_code == 409
        assert "already exists" in r2.json()["detail"]

    def test_upload_replace_true_overwrites(self, app_with_empty_registry, valid_flow_data):
        r1 = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Original Name", "data": valid_flow_data},
            headers={"x-api-key": "test-key"},
        )
        assert r1.status_code == 201
        flow_id = r1.json()["id"]

        r2 = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Updated Name", "data": valid_flow_data, "replace": True},
            headers={"x-api-key": "test-key"},
        )
        assert r2.status_code == 201
        assert r2.json()["id"] == flow_id
        assert r2.json()["name"] == "Updated Name"

        flows = app_with_empty_registry.get("/flows").json()
        ids = [f["id"] for f in flows]
        assert ids.count(flow_id) == 1

    def test_upload_with_description(self, app_with_empty_registry, valid_flow_data):
        response = app_with_empty_registry.post(
            "/flows/upload/",
            json={"name": "Flow", "data": valid_flow_data, "description": "my desc"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 201
        assert response.json()["description"] == "my desc"
