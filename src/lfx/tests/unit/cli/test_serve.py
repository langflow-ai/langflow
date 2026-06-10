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
    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key-123"}):  # pragma: allowlist secret
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


def test_create_multi_serve_app_unknown_flow_id_returns_404(mock_graph, test_flow_meta):
    from lfx.cli.serve_app import FlowRegistry

    registry = FlowRegistry()
    registry.add(mock_graph, test_flow_meta)

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
        app = create_multi_serve_app(registry=registry)
        client = TestClient(app)

        response = client.get("/flows/does-not-exist/info", headers={"x-api-key": "test-key"})
        assert response.status_code == 404

        response = client.post(
            "/flows/does-not-exist/run",
            json={"input_value": "test"},
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 404


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
            patch("lfx.cli.commands.load_flow_from_json") as mock_load,
            patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            import typer
            from lfx.cli.commands import serve_command
            from typer.testing import CliRunner

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
            result = runner.invoke(app, [temp_path, "--verbose"])

            assert result.exit_code == 0, result.stdout

            # Should start the server
            assert mock_uvicorn.called
            mock_load.assert_called_once()

            # Check that the mock was called with the parsed JSON dict (not a path)
            args, _kwargs = mock_load.call_args
            assert isinstance(args[0], dict)

    finally:
        Path(temp_path).unlink()


def test_serve_command_inline_json():
    """Test serve command with inline JSON."""
    flow_json = '{"nodes": [], "edges": []}'

    with (
        patch("lfx.cli.commands.load_flow_from_json") as mock_load,
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
    ):
        import typer
        from lfx.cli.commands import serve_command
        from typer.testing import CliRunner

        # Create a mock graph
        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.nodes = {}
        mock_load.return_value = mock_graph

        # Create CLI app
        app = typer.Typer()
        app.command()(serve_command)

        runner = CliRunner()
        result = runner.invoke(app, ["--flow-json", flow_json, "--verbose"])

        assert result.exit_code == 0, result.stdout

        # Should start the server
        assert mock_uvicorn.called
        mock_load.assert_called_once()

        # Check that the mock was called with the parsed JSON dict (not a temp file path)
        args, _kwargs = mock_load.call_args
        assert isinstance(args[0], dict)


class TestBuildRegistryFromDirectory:
    def test_loads_all_json_files(self, tmp_path):
        import asyncio

        from lfx.cli.commands import build_registry_from_directory

        flow_data = {"nodes": [], "edges": []}
        (tmp_path / "a.json").write_text(json.dumps(flow_data))
        (tmp_path / "b.json").write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None

        with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
            registry = asyncio.run(build_registry_from_directory(tmp_path, lambda _: None, check_variables=False))

        assert len(registry) == 2

    def test_empty_directory_raises(self, tmp_path):
        import asyncio

        from lfx.cli.commands import build_registry_from_directory

        with pytest.raises(ValueError, match=r"No \.json files found"):
            asyncio.run(build_registry_from_directory(tmp_path, lambda _: None, check_variables=False))

    def test_non_json_files_ignored(self, tmp_path):
        import asyncio

        from lfx.cli.commands import build_registry_from_directory

        (tmp_path / "notes.txt").write_text("ignore me")
        flow_data = {"nodes": [], "edges": []}
        (tmp_path / "flow.json").write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None

        with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
            registry = asyncio.run(build_registry_from_directory(tmp_path, lambda _: None, check_variables=False))

        assert len(registry) == 1

    def test_failed_file_raises_with_filename(self, tmp_path):
        import asyncio

        from lfx.cli.commands import build_registry_from_directory

        (tmp_path / "bad.json").write_text('{"nodes": [], "edges": []}')

        with (
            patch("lfx.cli.commands.load_flow_from_json", side_effect=ValueError("corrupt")),
            pytest.raises(ValueError, match=r"bad\.json"),
        ):
            asyncio.run(build_registry_from_directory(tmp_path, lambda _: None, check_variables=False))


class TestBuildRegistryFromPaths:
    def test_loads_explicit_paths(self, tmp_path):
        import asyncio

        from lfx.cli.commands import build_registry_from_paths

        flow_data = {"nodes": [], "edges": []}
        p1 = tmp_path / "flow1.json"
        p2 = tmp_path / "flow2.json"
        p1.write_text(json.dumps(flow_data))
        p2.write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None

        with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
            registry = asyncio.run(build_registry_from_paths([p1, p2], lambda _: None, check_variables=False))

        assert len(registry) == 2

    def test_failed_path_raises_with_filename(self, tmp_path):
        import asyncio

        from lfx.cli.commands import build_registry_from_paths

        p = tmp_path / "bad.json"
        p.write_text('{"nodes": [], "edges": []}')

        with (
            patch("lfx.cli.commands.load_flow_from_json", side_effect=ValueError("oops")),
            pytest.raises(ValueError, match=r"bad\.json"),
        ):
            asyncio.run(build_registry_from_paths([p], lambda _: None, check_variables=False))

    def test_same_filename_in_different_dirs_gets_distinct_ids(self, tmp_path):
        """Regression: lfx serve a/flow.json b/flow.json must not collide on ID."""
        import asyncio

        from lfx.cli.commands import build_registry_from_paths

        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        flow_data = {"nodes": [], "edges": []}
        p1 = dir_a / "flow.json"
        p2 = dir_b / "flow.json"
        p1.write_text(json.dumps(flow_data))
        p2.write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None

        with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
            registry = asyncio.run(build_registry_from_paths([p1, p2], lambda _: None, check_variables=False))

        assert len(registry) == 2, "both flows must be registered with distinct IDs"


class TestServeCommandMultiFlow:
    def test_serve_command_with_directory(self, tmp_path):
        from lfx.cli.commands import serve_command

        flow_data = {"nodes": [], "edges": []}
        (tmp_path / "flow1.json").write_text(json.dumps(flow_data))
        (tmp_path / "flow2.json").write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None
        mock_graph.nodes = {}
        mock_graph.edges = []

        with (
            patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph),
            patch("lfx.cli.commands.uvicorn.run"),
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            import typer
            from typer.testing import CliRunner

            app = typer.Typer()
            app.command()(serve_command)
            runner = CliRunner()
            result = runner.invoke(app, [str(tmp_path)])

        assert result.exit_code == 0, result.output

    def test_serve_command_with_multiple_files(self, tmp_path):
        from lfx.cli.commands import serve_command

        flow_data = {"nodes": [], "edges": []}
        p1 = tmp_path / "flow1.json"
        p2 = tmp_path / "flow2.json"
        p1.write_text(json.dumps(flow_data))
        p2.write_text(json.dumps(flow_data))

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None
        mock_graph.nodes = {}
        mock_graph.edges = []

        with (
            patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph),
            patch("lfx.cli.commands.uvicorn.run"),
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            import typer
            from typer.testing import CliRunner

            app = typer.Typer()
            app.command()(serve_command)
            runner = CliRunner()
            result = runner.invoke(app, [str(p1), str(p2)])

        assert result.exit_code == 0, result.output

    def test_serve_command_empty_directory_exits_nonzero(self, tmp_path):
        from lfx.cli.commands import serve_command

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
            import typer
            from typer.testing import CliRunner

            app = typer.Typer()
            app.command()(serve_command)
            runner = CliRunner()
            result = runner.invoke(app, [str(tmp_path)])

        assert result.exit_code != 0


class TestPythonScriptServe:
    def test_load_graph_and_meta_dispatches_to_script_loader_for_py(self, tmp_path):
        """_load_graph_and_meta must call load_graph_from_script for .py files, not load_flow_from_json."""
        import asyncio

        from lfx.cli.commands import _load_graph_and_meta

        script = tmp_path / "my_flow.py"
        script.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None

        # load_graph_from_script is lazily imported inside _load_graph_and_meta,
        # so patch its module-level name directly.
        with (
            patch("lfx.cli.commands.load_graph_from_script", new=AsyncMock(return_value=mock_graph)) as mock_script,
            patch("lfx.cli.commands.find_graph_variable", return_value={"source": "x", "type": "Graph", "line": 1}),
            patch("lfx.cli.commands.load_flow_from_json") as mock_json,
        ):
            _graph, meta, raw_json = asyncio.run(_load_graph_and_meta(script, tmp_path, check_variables=False))

        mock_json.assert_not_called()
        mock_script.assert_called_once_with(script)
        assert raw_json is None
        assert meta.title == "my_flow"
        assert meta.relative_path == "my_flow.py"

    def test_serve_command_accepts_py_file(self, tmp_path):
        """Lfx serve my_script.py must not be rejected as an unsupported file type."""
        from lfx.cli.commands import serve_command

        script = tmp_path / "my_flow.py"
        script.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.prepare = MagicMock()
        mock_graph.flow_id = None
        mock_graph.nodes = {}
        mock_graph.edges = []

        with (
            patch("lfx.cli.commands.load_graph_from_script", new=AsyncMock(return_value=mock_graph)),
            patch("lfx.cli.commands.find_graph_variable", return_value={"type": "assignment", "line": 1}),
            patch("lfx.cli.commands.uvicorn.run"),
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            import typer
            from typer.testing import CliRunner

            app = typer.Typer()
            app.command()(serve_command)
            result = CliRunner().invoke(app, [str(script)])

        assert result.exit_code == 0, result.output

    def test_serve_command_rejects_unsupported_extension(self, tmp_path):
        """Non-.json/.py files must exit with an error."""
        from lfx.cli.commands import serve_command

        bad = tmp_path / "flow.txt"
        bad.write_text("not a flow")

        with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
            import typer
            from typer.testing import CliRunner

            app = typer.Typer()
            app.command()(serve_command)
            result = CliRunner().invoke(app, [str(bad)])

        assert result.exit_code != 0
        assert ".json or .py" in result.output


def test_build_registry_from_paths_no_env_fallback_stamps_graphs(tmp_path):
    """build_registry_from_paths with no_env_fallback=True must stamp each graph's context."""
    import asyncio

    from lfx.cli.commands import build_registry_from_paths

    p = tmp_path / "flow.json"
    p.write_text(json.dumps({"nodes": [], "edges": []}))

    mock_graph = MagicMock()
    mock_graph.prepare = MagicMock()
    mock_graph.flow_id = None
    mock_graph.context = {}

    with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
        registry = asyncio.run(
            build_registry_from_paths([p], lambda _: None, check_variables=False, no_env_fallback=True)
        )
    flow_id = registry.list_metas()[0].id
    graph, _ = registry.get(flow_id)
    assert graph.context.get("no_env_fallback") is True


def test_build_registry_from_paths_default_does_not_stamp(tmp_path):
    """build_registry_from_paths without no_env_fallback must not stamp the context."""
    import asyncio

    from lfx.cli.commands import build_registry_from_paths

    p = tmp_path / "flow.json"
    p.write_text(json.dumps({"nodes": [], "edges": []}))

    mock_graph = MagicMock()
    mock_graph.prepare = MagicMock()
    mock_graph.flow_id = None
    mock_graph.context = {}

    with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
        registry = asyncio.run(build_registry_from_paths([p], lambda _: None, check_variables=False))
    flow_id = registry.list_metas()[0].id
    graph, _ = registry.get(flow_id)
    assert not graph.context.get("no_env_fallback")


def test_build_registry_from_directory_no_env_fallback_stamps_graphs(tmp_path):
    """build_registry_from_directory with no_env_fallback=True must stamp each graph's context."""
    import asyncio

    from lfx.cli.commands import build_registry_from_directory

    p = tmp_path / "flow.json"
    p.write_text(json.dumps({"nodes": [], "edges": []}))

    mock_graph = MagicMock()
    mock_graph.prepare = MagicMock()
    mock_graph.flow_id = None
    mock_graph.context = {}

    with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
        registry = asyncio.run(
            build_registry_from_directory(tmp_path, lambda _: None, check_variables=False, no_env_fallback=True)
        )
    flow_id = registry.list_metas()[0].id
    graph, _ = registry.get(flow_id)
    assert graph.context.get("no_env_fallback") is True


def test_build_registry_from_directory_default_does_not_stamp(tmp_path):
    """build_registry_from_directory without no_env_fallback must not stamp the context."""
    import asyncio

    from lfx.cli.commands import build_registry_from_directory

    p = tmp_path / "flow.json"
    p.write_text(json.dumps({"nodes": [], "edges": []}))

    mock_graph = MagicMock()
    mock_graph.prepare = MagicMock()
    mock_graph.flow_id = None
    mock_graph.context = {}

    with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
        registry = asyncio.run(build_registry_from_directory(tmp_path, lambda _: None, check_variables=False))
    flow_id = registry.list_metas()[0].id
    graph, _ = registry.get(flow_id)
    assert not graph.context.get("no_env_fallback")


def test_build_registry_from_paths_passes_raw_json_to_store():
    """build_registry_from_paths must pass raw_json so JSON flows are written to the store."""
    import asyncio
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from lfx.cli.commands import build_registry_from_paths
    from lfx.cli.flow_store import NullFlowStore

    written = {}

    class SpyStore(NullFlowStore):
        def write(self, flow_id, flow_json):
            written[flow_id] = flow_json

    flow_data = {"name": "Test", "description": "", "data": {"nodes": [], "edges": []}}
    mock_graph = MagicMock()
    mock_graph.context = {}

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "flow.json"
        p.write_text(json.dumps(flow_data))
        with patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph):
            registry = asyncio.run(
                build_registry_from_paths([p], lambda _: None, check_variables=False, store=SpyStore())
            )

    assert len(written) == 1
    flow_id = registry.list_metas()[0].id
    assert written[flow_id]["name"] == "Test"


def test_build_registry_from_paths_py_file_skips_store():
    """.py flows must not write to the store (no raw JSON round-trip)."""
    import asyncio
    import tempfile
    from pathlib import Path
    from unittest.mock import AsyncMock, MagicMock, patch

    from lfx.cli.commands import build_registry_from_paths
    from lfx.cli.flow_store import NullFlowStore

    written = {}

    class SpyStore(NullFlowStore):
        def write(self, flow_id, flow_json):
            written[flow_id] = flow_json

    mock_graph = MagicMock()
    mock_graph.context = {}

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "flow.py"
        p.write_text("graph = None\n")
        with (
            patch("lfx.cli.commands.load_graph_from_script", new=AsyncMock(return_value=mock_graph)),
            patch("lfx.cli.commands.find_graph_variable", return_value={"source": "x", "type": "Graph", "line": 1}),
        ):
            asyncio.run(build_registry_from_paths([p], lambda _: None, check_variables=False, store=SpyStore()))

    assert written == {}


def test_startup_scan_store_flows_accessible_lazily(tmp_path):
    """build_registry_from_paths() does NOT call warm_from_store() — that is serve_command's job.

    Pre-existing store flows are NOT eagerly loaded by the builder but are counted
    via list_metas() and accessible on first get().  serve_command adds the
    warm_from_store() call for single-worker mode after build_registry_from_paths returns.
    """
    import asyncio
    from unittest.mock import MagicMock, patch

    from lfx.cli.commands import build_registry_from_paths
    from lfx.cli.flow_store import FilesystemFlowStore

    store = FilesystemFlowStore(tmp_path)
    raw = {"name": "Pre-existing", "description": None, "data": {"nodes": [], "edges": []}, "id": "pre-existing-id"}
    store.write("pre-existing-id", raw)

    mock_graph = MagicMock()
    mock_graph.context = {}

    with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
        registry = asyncio.run(build_registry_from_paths([], lambda _: None, check_variables=False, store=store))

    # Builder does NOT eagerly pre-warm — that's serve_command's responsibility
    assert "pre-existing-id" not in registry._flows

    # Counted by len() / list_metas() even before warm_from_store() is called
    assert len(registry) == 1

    # Accessible via get() which triggers lazy load (simulating serve_command's warm_from_store)
    with patch("lfx.cli.serve_app.load_flow_from_json", return_value=mock_graph):
        result = registry.get("pre-existing-id")
    assert result is not None
    assert result[1].title == "Pre-existing"


def test_serve_command_passes_workers_to_uvicorn():
    """--workers N must be forwarded to uvicorn.run as the workers argument."""
    import json
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from lfx.cli.commands import serve_command

    flow_data = {"name": "Test", "description": "", "data": {"nodes": [], "edges": []}}
    mock_graph = MagicMock()
    mock_graph.context = {}

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "flow.json"
        p.write_text(json.dumps(flow_data))
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
            patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph),
            patch("lfx.cli.commands.uvicorn.run") as mock_run,
        ):
            serve_command(
                script_paths=[str(p)],
                host="127.0.0.1",
                port=9999,
                workers=4,
                verbose=False,
                env_file=None,
                log_level="warning",
                flow_json=None,
                flow_dir=None,
                stdin=False,
                check_variables=False,
                no_env_fallback=False,
            )

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0]
    call_kwargs = mock_run.call_args[1] if mock_run.call_args[1] else {}
    assert call_kwargs.get("workers") == 4
    # For workers > 1, the app must be the factory import string, not an object
    assert call_args[0] == "lfx.cli.serve_app:create_serve_app"
    # The factory=True flag is required so uvicorn calls create_serve_app() at
    # worker startup, not at request time.
    assert call_kwargs.get("factory") is True


def test_serve_command_sets_startup_paths_env_for_multi_worker(tmp_path):
    """serve_command must set LFX_SERVE_STARTUP_PATHS so each worker can reload flows."""
    import json
    import os
    from unittest.mock import MagicMock, patch

    from lfx.cli.commands import serve_command
    from lfx.cli.serve_app import _SERVE_STARTUP_PATHS_ENV

    flow_data = {"name": "Test", "description": "", "data": {"nodes": [], "edges": []}}
    mock_graph = MagicMock()
    mock_graph.context = {}

    captured_env: dict = {}

    def capture_env(*_a, **_kw):
        captured_env.update(os.environ)

    p = tmp_path / "flow.json"
    p.write_text(json.dumps(flow_data))

    with (
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph),
        patch("lfx.cli.commands.uvicorn.run", side_effect=capture_env),
    ):
        serve_command(
            script_paths=[str(p)],
            host="127.0.0.1",
            port=9999,
            workers=2,
            verbose=False,
            env_file=None,
            log_level="warning",
            flow_json=None,
            flow_dir=None,
            stdin=False,
            check_variables=False,
            no_env_fallback=False,
        )

    assert _SERVE_STARTUP_PATHS_ENV in captured_env, "LFX_SERVE_STARTUP_PATHS must be set before uvicorn.run()"
    paths = json.loads(captured_env[_SERVE_STARTUP_PATHS_ENV])
    assert len(paths) == 1
    assert paths[0].endswith("flow.json"), f"expected flow.json in paths, got {paths}"
    # Must be cleaned up after uvicorn exits
    assert _SERVE_STARTUP_PATHS_ENV not in os.environ, "LFX_SERVE_STARTUP_PATHS must be cleaned up after server exits"


def test_serve_command_does_not_set_startup_paths_when_flow_dir_set(tmp_path):
    """When --flow-dir is set, LFX_SERVE_STARTUP_PATHS must be empty.

    Workers load startup flows via warm_from_store() (parent persisted them to
    the store).  Sending file paths would cause each worker to re-load and re-write
    them redundantly, and would break the .py restriction logic.
    """
    import json
    import os
    from unittest.mock import MagicMock, patch

    from lfx.cli.commands import serve_command
    from lfx.cli.serve_app import _SERVE_STARTUP_PATHS_ENV

    flow_data = {"name": "Test", "description": "", "data": {"nodes": [], "edges": []}}
    mock_graph = MagicMock()
    mock_graph.context = {}

    captured_env: dict = {}

    def capture_env(*_a, **_kw):
        captured_env.update(os.environ)

    p = tmp_path / "flow.json"
    p.write_text(json.dumps(flow_data))

    with (
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph),
        patch("lfx.cli.commands.uvicorn.run", side_effect=capture_env),
    ):
        serve_command(
            script_paths=[str(p)],
            host="127.0.0.1",
            port=9999,
            workers=2,
            verbose=False,
            env_file=None,
            log_level="warning",
            flow_json=None,
            flow_dir=tmp_path / "store",  # flow_dir is set
            stdin=False,
            check_variables=False,
            no_env_fallback=False,
        )

    assert _SERVE_STARTUP_PATHS_ENV in captured_env, "env var must still be set (to empty list)"
    paths = json.loads(captured_env[_SERVE_STARTUP_PATHS_ENV])
    assert paths == [], f"startup paths must be empty when flow_dir is set, got {paths}"


def test_serve_command_warns_when_workers_gt1_without_flow_dir():
    """--workers > 1 without --flow-dir should emit a warning to stderr."""
    import json
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from lfx.cli.commands import serve_command

    flow_data = {"name": "Test", "description": "", "data": {"nodes": [], "edges": []}}
    mock_graph = MagicMock()
    mock_graph.context = {}

    stderr_output = []

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "flow.json"
        p.write_text(json.dumps(flow_data))
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
            patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph),
            patch("lfx.cli.commands.uvicorn.run"),
            patch("typer.echo", side_effect=lambda msg, **kw: stderr_output.append(msg) if kw.get("err") else None),
        ):
            serve_command(
                script_paths=[str(p)],
                host="127.0.0.1",
                port=9999,
                workers=2,
                verbose=False,
                env_file=None,
                log_level="warning",
                flow_json=None,
                flow_dir=None,
                stdin=False,
                check_variables=False,
                no_env_fallback=False,
            )

    assert any("--flow-dir" in msg for msg in stderr_output), (
        f"Expected a warning mentioning --flow-dir, got: {stderr_output}"
    )


def test_serve_command_rejects_py_with_multiple_workers(tmp_path):
    """.py startup files must be rejected when --workers > 1 (cannot persist to store)."""
    import os
    from unittest.mock import patch

    from lfx.cli.commands import serve_command

    script = tmp_path / "my_flow.py"
    script.write_text("graph = None")

    stderr_output = []

    with (
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        patch("lfx.cli.commands.uvicorn.run"),
        patch("typer.echo", side_effect=lambda msg, **kw: stderr_output.append(msg) if kw.get("err") else None),
    ):
        from click.exceptions import Exit as ClickExit

        with pytest.raises(ClickExit):
            serve_command(
                script_paths=[str(script)],
                host="127.0.0.1",
                port=9999,
                workers=2,
                verbose=False,
                env_file=None,
                log_level="warning",
                flow_json=None,
                flow_dir=tmp_path / "flows",
                stdin=False,
                check_variables=False,
                no_env_fallback=False,
            )

    assert any(".py" in msg and "cannot be used" in msg for msg in stderr_output), stderr_output


def test_serve_command_allows_py_with_multiple_workers_no_flow_dir(tmp_path):
    """.py files + --workers > 1 + no --flow-dir must be allowed.

    Each worker reloads the .py via LFX_SERVE_STARTUP_PATHS since there is no
    store.  The error only applies when --flow-dir is set (workers would skip
    startup paths and warm_from_store, missing the .py flow entirely).
    """
    import json
    import os
    from unittest.mock import AsyncMock, MagicMock, patch

    from lfx.cli.commands import serve_command
    from lfx.cli.serve_app import _SERVE_STARTUP_PATHS_ENV

    script = tmp_path / "my_flow.py"
    script.write_text("graph = None")

    mock_graph = MagicMock()
    mock_graph.context = {}
    captured_env: dict = {}

    def capture_env(*_a, **_kw):
        captured_env.update(os.environ)

    with (
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        patch("lfx.cli.commands.load_graph_from_script", new=AsyncMock(return_value=mock_graph)),
        patch("lfx.cli.commands.find_graph_variable", return_value={"type": "assignment", "line": 1}),
        patch("lfx.cli.commands.uvicorn.run", side_effect=capture_env),
    ):
        # Must NOT raise — .py without flow_dir is allowed for multi-worker
        serve_command(
            script_paths=[str(script)],
            host="127.0.0.1",
            port=9999,
            workers=2,
            verbose=False,
            env_file=None,
            log_level="warning",
            flow_json=None,
            flow_dir=None,  # no flow_dir — .py is allowed here
            stdin=False,
            check_variables=False,
            no_env_fallback=False,
        )

    # LFX_SERVE_STARTUP_PATHS must contain the .py path so workers can reload it
    assert _SERVE_STARTUP_PATHS_ENV in captured_env, "LFX_SERVE_STARTUP_PATHS must be set"
    paths = json.loads(captured_env[_SERVE_STARTUP_PATHS_ENV])
    assert any("my_flow.py" in p for p in paths), f"expected .py path in STARTUP_PATHS, got {paths}"


def test_serve_command_no_warning_when_workers_gt1_with_flow_dir(tmp_path):
    """--workers > 1 WITH --flow-dir must not emit the missing-store warning."""
    import json
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from lfx.cli.commands import serve_command

    flow_data = {"name": "Test", "description": "", "data": {"nodes": [], "edges": []}}
    mock_graph = MagicMock()
    mock_graph.context = {}

    stderr_output = []

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "flow.json"
        p.write_text(json.dumps(flow_data))
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
            patch("lfx.cli.commands.load_flow_from_json", return_value=mock_graph),
            patch("lfx.cli.commands.uvicorn.run"),
            patch("typer.echo", side_effect=lambda msg, **kw: stderr_output.append(msg) if kw.get("err") else None),
        ):
            serve_command(
                script_paths=[str(p)],
                host="127.0.0.1",
                port=9999,
                workers=2,
                verbose=False,
                env_file=None,
                log_level="warning",
                flow_json=None,
                flow_dir=tmp_path / "flows",
                stdin=False,
                check_variables=False,
                no_env_fallback=False,
            )

    assert not any("--flow-dir" in msg for msg in stderr_output)


# ---------------------------------------------------------------------------
# --upgrade-flow gate parity with `lfx run`
#
# `serve` and `run` share lfx.upgrade.cli_gate.apply_upgrade_gate; these tests
# mirror TestUpgradeFlowOption in tests/unit/run/test_base.py so the two entry
# points can't silently diverge. They target the release-1.10.0 registry-based
# serve: flows load via lfx.cli.commands.load_flow_from_json (which receives the
# parsed temp-file payload) and the server starts via uvicorn.run. The
# --upgrade-flow scope here is inline JSON, stdin, and a single .json file.
# ---------------------------------------------------------------------------

_UPGRADE_REGISTRY_CODE = "class MyComp:\n    pass  # v2"
_UPGRADE_NODE_CODE = "class MyComp:\n    pass  # v1"


def _upgrade_registry():
    return {
        "Cat": {
            "MyComp": {
                "template": {"code": {"value": _UPGRADE_REGISTRY_CODE}},
                "outputs": [{"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}],
                "metadata": {},
            }
        }
    }


def _upgrade_flow_json(code=_UPGRADE_NODE_CODE, type_="MyComp"):
    return json.dumps(
        {
            "nodes": [
                {
                    "id": "n1",
                    "data": {
                        "id": "n1",
                        "type": type_,
                        "node": {
                            "display_name": "My Component",
                            "template": {"code": {"value": code}},
                            "outputs": [
                                {"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}
                            ],
                        },
                    },
                }
            ],
            "edges": [],
        }
    )


def _upgrade_flow_json_enveloped(code=_UPGRADE_NODE_CODE, type_="MyComp"):
    """An exported-flow envelope wrapping the inner graph: {"name", "description", "data": {...}}."""
    inner = json.loads(_upgrade_flow_json(code=code, type_=type_))
    return json.dumps({"name": "My Flow", "description": "the flow", "data": inner})


def _upgrade_serve_app():
    import typer
    from lfx.cli.commands import serve_command

    app = typer.Typer()
    app.command()(serve_command)
    return app


def _upgrade_capturing_loader(captured: dict):
    """Side effect for a patched lfx.cli.commands.load_flow_from_json.

    The registry builder calls ``load_flow_from_json(raw_json)`` with the parsed temp-file
    payload, so capturing the first positional arg records exactly what serve wrote to disk
    for the loader (the real loader does ``flow_graph["data"]``, so the payload must be
    enveloped).
    """

    def _side_effect(payload, *_args, **_kwargs):
        captured["payload"] = payload
        graph = MagicMock()
        graph.prepare = MagicMock()
        graph.flow_id = None
        graph.nodes = {}
        graph.edges = []
        return graph

    return _side_effect


def test_serve_upgrade_flow_check_aborts_on_incompatible():
    """`serve --upgrade-flow=check` refuses to serve an outdated flow and never starts uvicorn."""
    from typer.testing import CliRunner

    with (
        patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=_upgrade_registry()),
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
    ):
        args = ["--flow-json", _upgrade_flow_json(), "--upgrade-flow", "check"]
        result = CliRunner().invoke(_upgrade_serve_app(), args)
        assert result.exit_code != 0
        assert not mock_uvicorn.called


def test_serve_upgrade_flow_safe_blocked_aborts():
    """`serve --upgrade-flow=safe` aborts when a component is blocked (not in the registry)."""
    from typer.testing import CliRunner

    with (
        patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value={}),
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
    ):
        args = ["--flow-json", _upgrade_flow_json(), "--upgrade-flow", "safe"]
        result = CliRunner().invoke(_upgrade_serve_app(), args)
        assert result.exit_code != 0
        assert not mock_uvicorn.called


def test_serve_upgrade_flow_bad_value_rejected():
    """An unrecognized --upgrade-flow value is rejected before serving."""
    from typer.testing import CliRunner

    with (
        patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=_upgrade_registry()),
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
    ):
        args = ["--flow-json", _upgrade_flow_json(), "--upgrade-flow", "typo"]
        result = CliRunner().invoke(_upgrade_serve_app(), args)
        assert result.exit_code != 0
        assert not mock_uvicorn.called


def test_serve_upgrade_flow_safe_proceeds_to_serve():
    """`serve --upgrade-flow=safe` applies safe upgrades and proceeds to start the server."""
    from typer.testing import CliRunner

    captured: dict = {}
    with (
        patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=_upgrade_registry()),
        patch("lfx.cli.commands.load_flow_from_json", side_effect=_upgrade_capturing_loader(captured)),
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
    ):
        args = ["--flow-json", _upgrade_flow_json(), "--upgrade-flow", "safe"]
        result = CliRunner().invoke(_upgrade_serve_app(), args)
        assert result.exit_code == 0, result.stdout
        assert mock_uvicorn.called

    # Bare inline graph gets wrapped by the gate so the loader can read flow_graph["data"],
    # and the node's v1 code was upgraded to the registry's v2 code.
    payload = captured["payload"]
    assert "data" in payload, payload
    assert payload["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == _UPGRADE_REGISTRY_CODE


def test_serve_upgrade_safe_inline_envelope_preserved_and_upgraded():
    """`serve --flow-json <enveloped> --upgrade-flow=safe` keeps outer metadata and upgrades the inner graph."""
    from typer.testing import CliRunner

    captured: dict = {}
    with (
        patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=_upgrade_registry()),
        patch("lfx.cli.commands.load_flow_from_json", side_effect=_upgrade_capturing_loader(captured)),
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
    ):
        args = ["--flow-json", _upgrade_flow_json_enveloped(), "--upgrade-flow", "safe"]
        result = CliRunner().invoke(_upgrade_serve_app(), args)
        assert result.exit_code == 0, result.stdout
        assert mock_uvicorn.called

    payload = captured["payload"]
    assert payload["name"] == "My Flow"  # outer metadata preserved through the upgrade
    assert payload["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == _UPGRADE_REGISTRY_CODE


def test_serve_upgrade_safe_stdin_envelope_preserved():
    """`serve --stdin <enveloped> --upgrade-flow=safe` keeps outer metadata and writes a loadable payload."""
    from typer.testing import CliRunner

    captured: dict = {}
    with (
        patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=_upgrade_registry()),
        patch("lfx.cli.commands.load_flow_from_json", side_effect=_upgrade_capturing_loader(captured)),
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
    ):
        result = CliRunner().invoke(
            _upgrade_serve_app(), ["--stdin", "--upgrade-flow", "safe"], input=_upgrade_flow_json_enveloped()
        )
        assert result.exit_code == 0, result.stdout
        assert mock_uvicorn.called

    payload = captured["payload"]
    assert "data" in payload, payload
    assert "nodes" in payload["data"], payload
    assert payload["name"] == "My Flow"


def test_serve_file_upgrade_safe_writes_enveloped_payload():
    """`serve <file.json> --upgrade-flow=safe` unwraps the file, upgrades, and feeds a loadable payload."""
    from typer.testing import CliRunner

    envelope = json.loads(_upgrade_flow_json_enveloped())
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(envelope, f)
        flow_path = f.name

    captured: dict = {}
    try:
        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=_upgrade_registry()),
            patch("lfx.cli.commands.load_flow_from_json", side_effect=_upgrade_capturing_loader(captured)),
            patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            result = CliRunner().invoke(_upgrade_serve_app(), [flow_path, "--upgrade-flow", "safe"])
            assert result.exit_code == 0, result.stdout
            assert mock_uvicorn.called
    finally:
        Path(flow_path).unlink(missing_ok=True)

    payload = captured["payload"]
    assert payload["name"] == "My Flow"  # outer metadata preserved
    assert payload["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == _UPGRADE_REGISTRY_CODE


def test_serve_file_upgrade_rejects_py_script():
    """`serve <file.py> --upgrade-flow=...` is rejected — only JSON flows can be upgrade-checked."""
    from typer.testing import CliRunner

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("graph = None\n")
        py_path = f.name

    try:
        with (
            patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            result = CliRunner().invoke(_upgrade_serve_app(), [py_path, "--upgrade-flow", "check"])
            assert result.exit_code != 0
            assert not mock_uvicorn.called
    finally:
        Path(py_path).unlink(missing_ok=True)


def test_serve_upgrade_rejects_multiple_paths():
    """`--upgrade-flow` with more than one path is rejected (single .json only)."""
    from typer.testing import CliRunner

    paths = []
    try:
        for _ in range(2):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(json.loads(_upgrade_flow_json_enveloped()), f)
                paths.append(f.name)
        with (
            patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
            patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
        ):
            result = CliRunner().invoke(_upgrade_serve_app(), [*paths, "--upgrade-flow", "safe"])
            assert result.exit_code != 0
            assert not mock_uvicorn.called
    finally:
        for p in paths:
            Path(p).unlink(missing_ok=True)


def test_serve_upgrade_requires_a_flow_source():
    """`--upgrade-flow` with no flow source (no paths, --flow-json, or --stdin) is rejected."""
    from typer.testing import CliRunner

    with (
        patch("lfx.cli.commands.uvicorn.run") as mock_uvicorn,
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}),  # pragma: allowlist secret
    ):
        result = CliRunner().invoke(_upgrade_serve_app(), ["--upgrade-flow", "check"])
        assert result.exit_code != 0
        assert not mock_uvicorn.called
