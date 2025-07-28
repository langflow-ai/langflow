"""Tests for LFX serve command."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lfx.cli.common import (
    flow_id_from_path,
    get_api_key,
    get_best_access_host,
    get_free_port,
    is_port_in_use,
)
from lfx.cli.serve_app import FlowMeta, create_multi_serve_app


def test_is_port_in_use():
    """Test port availability checking."""
    # Port 0 should always be available (OS assigns)
    assert not is_port_in_use(0)

    # Very high ports are likely available
    assert not is_port_in_use(65123)


def test_get_free_port():
    """Test finding a free port."""
    port = get_free_port(8000)
    assert 8000 <= port < 65535
    assert not is_port_in_use(port)


def test_get_best_access_host():
    """Test host resolution for display."""
    assert get_best_access_host("0.0.0.0") == "localhost"
    assert get_best_access_host("") == "localhost"
    assert get_best_access_host("127.0.0.1") == "127.0.0.1"
    assert get_best_access_host("example.com") == "example.com"


def test_get_api_key_missing():
    """Test API key retrieval when not set."""
    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(
            ValueError,
            match="LANGFLOW_API_KEY environment variable is not set",
        ),
    ):
        get_api_key()


def test_get_api_key_present():
    """Test API key retrieval when set."""
    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key-123"}):
        assert get_api_key() == "test-key-123"


def test_flow_id_from_path():
    """Test deterministic flow ID generation."""
    root = Path("/tmp/flows")
    path1 = root / "flow1.json"
    path2 = root / "subdir" / "flow2.json"

    # Same path should always generate same ID
    id1a = flow_id_from_path(path1, root)
    id1b = flow_id_from_path(path1, root)
    assert id1a == id1b

    # Different paths should generate different IDs
    id2 = flow_id_from_path(path2, root)
    assert id1b != id2


@pytest.fixture
def mock_graph():
    """Create a mock graph for testing."""
    graph = MagicMock()
    graph.nodes = {"node1": MagicMock()}
    graph.prepare = MagicMock()
    graph.arun = AsyncMock(return_value=[])
    return graph


@pytest.fixture
def test_flow_meta():
    """Create test flow metadata."""
    return FlowMeta(
        id="test-flow-id",
        relative_path="test.json",
        title="Test Flow",
        description="A test flow",
    )


def test_create_multi_serve_app_single_flow(mock_graph, test_flow_meta):
    """Test creating app for single flow."""
    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):
        app = create_multi_serve_app(
            root_dir=Path("/tmp"),
            graphs={"test-flow-id": mock_graph},
            metas={"test-flow-id": test_flow_meta},
            verbose_print=lambda x: None,  # noqa: ARG005
        )

        client = TestClient(app)

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "flow_count": 1}

        # Test run endpoint without auth
        response = client.post("/flows/test-flow-id/run", json={"input_value": "test"})
        assert response.status_code == 401

        # Test run endpoint with auth
        response = client.post(
            "/flows/test-flow-id/run",
            json={"input_value": "test"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 200


def test_create_multi_serve_app_multiple_flows(mock_graph, test_flow_meta):
    """Test creating app for multiple flows."""
    meta2 = FlowMeta(
        id="flow-2",
        relative_path="flow2.json",
        title="Flow 2",
        description="Second flow",
    )

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):
        app = create_multi_serve_app(
            root_dir=Path("/tmp"),
            graphs={"test-flow-id": mock_graph, "flow-2": mock_graph},
            metas={"test-flow-id": test_flow_meta, "flow-2": meta2},
            verbose_print=lambda x: None,  # noqa: ARG005
        )

        client = TestClient(app)

        # Test flows listing
        response = client.get("/flows")
        assert response.status_code == 200
        flows = response.json()
        assert len(flows) == 2
        assert any(f["id"] == "test-flow-id" for f in flows)
        assert any(f["id"] == "flow-2" for f in flows)

        # Test individual flow run
        response = client.post(
            "/flows/test-flow-id/run",
            json={"input_value": "test"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 200

        # Test flow info
        response = client.get(
            "/flows/test-flow-id/info",
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == "test-flow-id"


def test_serve_command_json_file():
    """Test serve command with JSON file input."""
    # Create a temporary JSON flow file
    flow_data = {
        "nodes": [],
        "edges": [],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(flow_data, f)
        temp_path = f.name

    try:
        # Mock the necessary dependencies
        with (
            patch("lfx.cli.commands.load_graph_from_path") as mock_load,
            patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),
        ):
            import typer
            from typer.testing import CliRunner

            from lfx.cli.commands import serve_command

            # Create a mock graph
            mock_graph = MagicMock()
            mock_graph.prepare = MagicMock()
            # Mock nodes as a dictionary for graph analysis
            mock_node = MagicMock()
            mock_node.data = {
                "type": "TestComponent",
                "display_name": "Test Component",
                "description": "A test component",
                "template": {},
            }
            mock_graph.nodes = {"node1": mock_node}

            # Mock edges as a list
            mock_edge = MagicMock()
            mock_edge.source = "node1"
            mock_edge.target = "node2"
            mock_graph.edges = [mock_edge]
            mock_load.return_value = mock_graph

            # Create CLI app
            app = typer.Typer()
            app.command()(serve_command)

            runner = CliRunner()
            runner.invoke(app, [temp_path])

            # Should start the server
            assert mock_uvicorn.called
            assert mock_load.called

    finally:
        Path(temp_path).unlink()


def test_serve_command_inline_json():
    """Test serve command with inline JSON."""
    flow_json = '{"nodes": [], "edges": []}'

    with (
        patch("lfx.cli.commands.load_graph_from_path") as mock_load,
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),
    ):
        import typer
        from typer.testing import CliRunner

        from lfx.cli.commands import serve_command

        # Create a mock graph
        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.nodes = {}
        mock_load.return_value = mock_graph

        # Create CLI app
        app = typer.Typer()
        app.command()(serve_command)

        runner = CliRunner()
        runner.invoke(app, ["--flow-json", flow_json])

        # Should start the server
        assert mock_uvicorn.called
        assert mock_load.called
