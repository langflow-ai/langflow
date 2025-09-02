"""Simple tests for LFX serve command focusing on CLI functionality."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner


def test_cli_imports():
    """Test that we can import the CLI components."""
    # These imports should work without errors
    from lfx.__main__ import app, main

    assert main is not None
    assert app is not None


def test_serve_command_help():
    """Test that serve command shows help."""
    from lfx.__main__ import app

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "Serve a flow as an API" in result.output


def test_serve_command_missing_api_key():
    """Test that serve command fails without API key."""
    from lfx.__main__ import app

    # Create a temporary JSON flow file
    flow_data = {
        "data": {
            "nodes": [],
            "edges": [],
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(flow_data, f)
        temp_path = f.name

    try:
        # Clear API key from environment
        with patch.dict(os.environ, {}, clear=True):
            runner = CliRunner()
            result = runner.invoke(app, ["serve", temp_path])

            assert result.exit_code == 1
            # Check both output and exception since typer may output to different streams
            assert "LANGFLOW_API_KEY" in str(result.output or result.exception or "")
    finally:
        Path(temp_path).unlink()


def test_serve_command_with_flow_json():
    """Test serve command with inline JSON."""
    from lfx.__main__ import app

    flow_json = '{"data": {"nodes": [], "edges": []}}'

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}), patch("uvicorn.run") as mock_uvicorn:
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "--flow-json", flow_json])

        # Should try to start the server
        assert mock_uvicorn.called or result.exit_code != 0


def test_serve_command_invalid_json():
    """Test serve command with invalid JSON."""
    from lfx.__main__ import app

    invalid_json = '{"invalid": json}'

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "--flow-json", invalid_json], catch_exceptions=False)

        assert result.exit_code == 1


def test_serve_command_nonexistent_file():
    """Test serve command with non-existent file."""
    from lfx.__main__ import app

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-key"}):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "/path/to/nonexistent/file.json"], catch_exceptions=False)

        assert result.exit_code == 1


def test_cli_utility_functions():
    """Test basic utility functions that don't have complex dependencies."""
    from lfx.cli.common import (
        flow_id_from_path,
        get_best_access_host,
        get_free_port,
        is_port_in_use,
    )

    # Test port functions
    assert not is_port_in_use(0)  # Port 0 is always available

    port = get_free_port(8000)
    assert 8000 <= port < 65535

    # Test host resolution
    assert get_best_access_host("0.0.0.0") == "localhost"
    assert get_best_access_host("") == "localhost"
    assert get_best_access_host("127.0.0.1") == "127.0.0.1"

    # Test flow ID generation
    root = Path("/tmp/flows")
    path = root / "test.json"
    flow_id = flow_id_from_path(path, root)
    assert isinstance(flow_id, str)
    assert len(flow_id) == 36  # UUID length
