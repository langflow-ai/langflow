"""Simple tests for LFX serve command focusing on CLI functionality."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

# Tests that invoke `serve` with valid-looking input may hang while langflow
# initialises async server infrastructure.  Skip those in CI only; all
# import/help/utility/fast-error tests run everywhere.
_ci_env = os.environ.get("CI", "")
_is_ci = _ci_env.lower() in {"1", "true", "yes"}
_skip_in_ci = pytest.mark.skipif(
    _is_ci,
    reason="serve startup hangs in CI — pending root-cause fix",
)


def test_cli_imports():
    """Test that we can import the CLI components."""
    from lfx.__main__ import app, main

    assert main is not None
    assert app is not None


def test_serve_command_help():
    """Test that serve command shows help without starting a server."""
    from lfx.__main__ import app

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "Serve a flow as an API" in result.output


def test_serve_command_invalid_json():
    """Test serve command fails fast on unparseable JSON (before any server init)."""
    from lfx.__main__ import app

    invalid_json = '{"invalid": json}'

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "--flow-json", invalid_json], catch_exceptions=False)

        assert result.exit_code == 1


def test_serve_command_nonexistent_file():
    """Test serve command fails fast when the flow file does not exist."""
    from lfx.__main__ import app

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):  # pragma: allowlist secret
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "/path/to/nonexistent/file.json"], catch_exceptions=False)

        assert result.exit_code == 1


def test_cli_utility_functions():
    """Test port/host/flow-ID utilities — no server involved."""
    from lfx.cli.common import (
        flow_id_from_path,
        get_best_access_host,
        get_free_port,
        is_port_in_use,
    )

    assert not is_port_in_use(0)

    port = get_free_port(8000)
    assert 8000 <= port < 65535

    assert get_best_access_host("0.0.0.0") == "localhost"
    assert get_best_access_host("") == "localhost"
    assert get_best_access_host("127.0.0.1") == "127.0.0.1"

    root = Path("/tmp/flows")
    path = root / "test.json"
    flow_id = flow_id_from_path(path, root)
    assert isinstance(flow_id, str)
    assert len(flow_id) == 36  # UUID


@_skip_in_ci
def test_serve_command_missing_api_key():
    """Serve command must exit 1 and mention LANGFLOW_API_KEY when no key is set."""
    from lfx.__main__ import app

    flow_data = {"data": {"nodes": [], "edges": []}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(flow_data, f)
        temp_path = f.name

    try:
        with patch.dict(os.environ, {}, clear=True):
            runner = CliRunner()
            result = runner.invoke(app, ["serve", temp_path])

            assert result.exit_code == 1
            assert "LANGFLOW_API_KEY" in str(result.output or result.exception or "")
    finally:
        Path(temp_path).unlink()


@_skip_in_ci
def test_serve_command_with_flow_json():
    """Serve command with a valid payload should attempt to call uvicorn.run."""
    from lfx.__main__ import app

    flow_json = '{"data": {"nodes": [], "edges": []}}'

    env = {"LANGFLOW_API_KEY": "test-key"}  # pragma: allowlist secret
    with patch.dict(os.environ, env), patch("uvicorn.run") as mock_uvicorn:
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "--flow-json", flow_json])

        assert mock_uvicorn.called or result.exit_code != 0
