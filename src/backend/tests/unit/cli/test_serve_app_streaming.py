"""Unit tests for streaming functionality in multi-serve app."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.cli.serve_app import FlowMeta, StreamRequest, create_multi_serve_app


class MockNode:
    """Mock node for testing graph structure."""

    def __init__(self, node_id: str, node_type: str = "TestComponent", display_name: str | None = None):
        self.data = {
            "id": node_id,
            "type": node_type,
            "display_name": display_name or node_type,
            "description": f"Mock {node_type} component",
            "template": {
                "input_field": {"type": "str", "value": "default_value"},
                "output_field": {"type": "str", "value": ""},
            },
        }


class MockEdge:
    """Mock edge for testing graph structure."""

    def __init__(self, source: str, target: str):
        self.source = source
        self.target = target


class MockGraph:
    """Mock graph for testing."""

    def __init__(self, nodes=None, edges=None):
        self.nodes = nodes or {
            "input_node": MockNode("input_node", "ChatInput", "Chat Input"),
            "output_node": MockNode("output_node", "ChatOutput", "Chat Output"),
        }
        self.edges = edges or [MockEdge("input_node", "output_node")]


@pytest.fixture
def mock_graphs():
    """Create mock graphs for testing."""
    return {
        "flow1": MockGraph(),
        "flow2": MockGraph(
            nodes={
                "text_input": MockNode("text_input", "TextInput", "Text Input"),
                "processor": MockNode("processor", "Processor", "Text Processor"),
                "text_output": MockNode("text_output", "TextOutput", "Text Output"),
            },
            edges=[MockEdge("text_input", "processor"), MockEdge("processor", "text_output")],
        ),
    }


@pytest.fixture
def mock_metas():
    """Create mock metadata for testing."""
    return {
        "flow1": FlowMeta(
            id="flow1", relative_path="flow1.json", title="Test Flow 1", description="A simple test flow for chat"
        ),
        "flow2": FlowMeta(
            id="flow2", relative_path="flow2.json", title="Test Flow 2", description="A test flow with text processing"
        ),
    }


@pytest.fixture
def multi_serve_app(mock_graphs, mock_metas, monkeypatch):
    """Create a multi-serve app for testing."""
    # Set required environment variable
    monkeypatch.setenv("LANGFLOW_API_KEY", "test-api-key")

    with patch("langflow.cli.serve_app.execute_graph_with_capture") as mock_execute:
        # Mock successful execution
        mock_execute.return_value = (
            [{"result": "Test response", "type": "message"}],
            "Execution completed successfully",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_multi_serve_app(
                root_dir=Path(temp_dir), graphs=mock_graphs, metas=mock_metas, verbose_print=lambda _: None
            )

            # Override the dependency after app creation
            def mock_verify_api_key(query_param: str | None = None, header_param: str | None = None) -> str:  # noqa: ARG001
                return "test-api-key"

            # Import the original dependency
            from langflow.cli.commands import verify_api_key

            app.dependency_overrides[verify_api_key] = mock_verify_api_key

            yield app

            # Clean up
            app.dependency_overrides.clear()


@pytest.fixture
def mock_api_key(monkeypatch):
    """Mock API key for authentication."""
    # Set the required environment variable
    monkeypatch.setenv("LANGFLOW_API_KEY", "test-api-key")

    with patch("langflow.cli.commands.verify_api_key") as mock_verify:
        mock_verify.return_value = True
        yield "test-api-key"


class TestMultiServeStreaming:
    """Test cases for multi-serve streaming functionality."""

    async def test_stream_endpoint_exists(self, multi_serve_app, mock_api_key):
        """Test that streaming endpoints are properly created."""
        async with (
            LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
        ):
            # Test that stream endpoints exist for each flow
            response = await client.post(
                "/flows/flow1/stream", json={"input_value": "Hello, world!"}, headers={"x-api-key": mock_api_key}
            )
            # Should not be 404 (endpoint exists)
            assert response.status_code != 404

    async def test_stream_basic_functionality(self, multi_serve_app, mock_api_key):
        """Test basic streaming functionality."""
        with patch("langflow.cli.serve_app.run_flow_generator_for_serve") as mock_generator:
            # Mock the streaming generator
            async def mock_stream_generator(*args, **kwargs):  # noqa: ARG001
                event_manager = kwargs.get("event_manager")
                client_consumed_queue = kwargs.get("client_consumed_queue")
                if event_manager:
                    event_manager.on_end(data={"result": {"result": "Streamed response", "success": True}})
                    await client_consumed_queue.get()
                    # Send the final None to close the stream
                    await event_manager.queue.put((None, None, 0))

            mock_generator.side_effect = mock_stream_generator

            async with (
                LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
                AsyncClient(
                    transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True
                ) as client,
            ):
                response = await client.post(
                    "/flows/flow1/stream",
                    json={"input_value": "Test streaming input"},
                    headers={"x-api-key": mock_api_key},
                )

                # Debug output removed to pass linting

                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    async def test_stream_request_validation(self, multi_serve_app, mock_api_key):
        """Test StreamRequest model validation."""
        async with (
            LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
        ):
            # Test with minimal valid request
            response = await client.post(
                "/flows/flow1/stream", json={"input_value": "test"}, headers={"x-api-key": mock_api_key}
            )
            assert response.status_code == 200

            # Test with full request
            response = await client.post(
                "/flows/flow1/stream",
                json={
                    "input_value": "test input",
                    "input_type": "chat",
                    "output_type": "chat",
                    "session_id": "test-session-123",
                    "tweaks": {"component1": {"param1": "value1"}},
                },
                headers={"x-api-key": mock_api_key},
            )
            assert response.status_code == 200

    async def test_stream_authentication_required(self, multi_serve_app):
        """Test that streaming endpoints require authentication."""
        async with (
            LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
        ):
            # Test without API key
            response = await client.post("/flows/flow1/stream", json={"input_value": "test"})
            # Should fail authentication
            assert response.status_code in [401, 403]

    async def test_stream_flow_not_found(self, multi_serve_app, mock_api_key):
        """Test streaming with non-existent flow."""
        async with (
            LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
        ):
            response = await client.post(
                "/flows/nonexistent/stream", json={"input_value": "test"}, headers={"x-api-key": mock_api_key}
            )
            assert response.status_code == 404

    async def test_stream_error_handling(self, multi_serve_app, mock_api_key):
        """Test error handling in streaming endpoint."""
        with patch("langflow.cli.serve_app.run_flow_generator_for_serve") as mock_generator:
            # Mock an error in the generator
            async def mock_error_generator(*args, **kwargs):  # noqa: ARG001
                msg = "Test error during streaming"
                raise RuntimeError(msg)

            mock_generator.side_effect = mock_error_generator

            async with (
                LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
                AsyncClient(
                    transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True
                ) as client,
            ):
                response = await client.post(
                    "/flows/flow1/stream", json={"input_value": "test"}, headers={"x-api-key": mock_api_key}
                )

                # Should still return 200 but with error stream
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    async def test_stream_multiple_flows(self, multi_serve_app, mock_api_key):
        """Test streaming with multiple flows."""
        async with (
            LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
        ):
            # Test streaming for flow1
            response1 = await client.post(
                "/flows/flow1/stream", json={"input_value": "test flow 1"}, headers={"x-api-key": mock_api_key}
            )
            assert response1.status_code == 200

            # Test streaming for flow2
            response2 = await client.post(
                "/flows/flow2/stream", json={"input_value": "test flow 2"}, headers={"x-api-key": mock_api_key}
            )
            assert response2.status_code == 200

    async def test_regular_run_endpoint_still_works(self, multi_serve_app, mock_api_key):
        """Test that regular run endpoints still work alongside streaming."""
        with patch("langflow.cli.serve_app.extract_result_data") as mock_extract:
            mock_extract.return_value = {
                "result": "Regular response",
                "success": True,
                "type": "message",
                "component": "test",
            }

            async with (
                LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
                AsyncClient(
                    transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True
                ) as client,
            ):
                response = await client.post(
                    "/flows/flow1/run", json={"input_value": "test regular run"}, headers={"x-api-key": mock_api_key}
                )

                assert response.status_code == 200
                assert response.headers["content-type"] == "application/json"
                data = response.json()
                assert data["result"] == "Regular response"
                assert data["success"] is True

    async def test_list_flows_endpoint(self, multi_serve_app):
        """Test that the flows listing endpoint works."""
        async with (
            LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
        ):
            response = await client.get("/flows")
            assert response.status_code == 200

            flows = response.json()
            assert len(flows) == 2
            assert any(flow["id"] == "flow1" for flow in flows)
            assert any(flow["id"] == "flow2" for flow in flows)

    def test_stream_request_model(self):
        """Test the StreamRequest model validation."""
        # Test minimal request
        request = StreamRequest(input_value="test")
        assert request.input_value == "test"
        assert request.input_type == "chat"  # default
        assert request.output_type == "chat"  # default
        assert request.session_id is None
        assert request.tweaks is None

        # Test full request
        request = StreamRequest(
            input_value="test input",
            input_type="text",
            output_type="debug",
            output_component="specific_component",
            session_id="session123",
            tweaks={"comp1": {"param1": "value1"}},
        )
        assert request.input_value == "test input"
        assert request.input_type == "text"
        assert request.output_type == "debug"
        assert request.output_component == "specific_component"
        assert request.session_id == "session123"
        assert request.tweaks == {"comp1": {"param1": "value1"}}

    async def test_concurrent_streaming(self, multi_serve_app, mock_api_key):
        """Test concurrent streaming requests."""
        async with (
            LifespanManager(multi_serve_app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
        ):
            # Start multiple concurrent streaming requests
            tasks = []
            for i in range(3):
                task = asyncio.create_task(
                    client.post(
                        "/flows/flow1/stream",
                        json={"input_value": f"concurrent test {i}"},
                        headers={"x-api-key": mock_api_key},
                    )
                )
                tasks.append(task)

            # Wait for all requests to complete
            responses = await asyncio.gather(*tasks)

            # All should be successful
            for response in responses:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
