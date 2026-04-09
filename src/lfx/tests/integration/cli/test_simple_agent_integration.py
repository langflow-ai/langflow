"""Integration tests for lfx CLI with Simple Agent flow.

These tests verify that the lfx CLI can properly load and execute the
Simple Agent starter project, addressing the bug where lfx serve/run
commands fail with module resolution errors.

Requirements:
- OPENAI_API_KEY environment variable must be set for execution tests
- Integration dependencies must be installed (use: uv sync --group integration)

Note on version compatibility:
- lfx requires langchain-core>=0.3.66,<1.0.0
- langchain-openai 1.x requires langchain-core 1.x which is incompatible
- When installing langchain-openai, use: langchain-openai>=0.3.0,<1.0.0
"""

import importlib.util
import json
import os
import re
import select
import signal

# Find a free port for testing
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from lfx.__main__ import app as lfx_app
from typer.testing import CliRunner

runner = CliRunner()


def has_integration_deps() -> bool:
    """Check if integration dependencies are installed."""
    required_modules = ["langchain_openai", "langchain_community", "bs4", "lxml"]
    return all(importlib.util.find_spec(module) is not None for module in required_modules)


# Skip all tests in this module if integration deps are not installed
pytestmark = pytest.mark.skipif(
    not has_integration_deps(),
    reason="Integration dependencies not installed. Run: uv sync --group integration",
)


def get_starter_projects_path() -> Path:
    """Get path to starter projects directory."""
    test_file_path = Path(__file__).resolve()
    current = test_file_path.parent
    while current != current.parent:
        starter_path = current / "src" / "backend" / "base" / "langflow" / "initial_setup" / "starter_projects"
        if starter_path.exists():
            return starter_path
        current = current.parent
    # Return an empty Path() if not found
    return Path()


def get_simple_agent_flow_path() -> Path:
    """Get path to Simple Agent starter project."""
    return get_starter_projects_path() / "Simple Agent.json"


def has_openai_api_key() -> bool:
    """Check if OPENAI_API_KEY is set."""
    key = os.getenv("OPENAI_API_KEY", "")
    return bool(key) and key != "dummy" and len(key) > 10


def parse_json_from_output(output: str, context: str = "output") -> dict:
    """Parse JSON from command output, searching in reverse if direct parsing fails.

    Args:
        output: The command output string to parse.
        context: Description of the output source for error messages.

    Returns:
        The parsed JSON as a dictionary.

    Raises:
        pytest.fail: If no valid JSON is found in the output.
    """
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        lines = output.split("\n")
        for line in reversed(lines):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        pytest.fail(f"No valid JSON in {context}: {output}")


class TestSimpleAgentFlowLoading:
    """Test that Simple Agent flow can be loaded without errors."""

    @pytest.fixture
    def simple_agent_flow_path(self) -> Path:
        """Get Simple Agent flow path, skip if not found."""
        path = get_simple_agent_flow_path()
        if not path.exists():
            pytest.skip(f"Simple Agent flow not found at {path}")
        return path

    def test_simple_agent_flow_loads_via_cli(self, simple_agent_flow_path: Path):
        """Test that lfx run can load the Simple Agent flow without critical errors."""
        result = runner.invoke(
            lfx_app,
            ["run", "--verbose", "--no-check-variables", str(simple_agent_flow_path), "test input"],
        )

        output = result.output

        # These are the critical errors that indicate structural problems
        critical_errors = [
            "No module named 'lfx.components",
            "No module named 'langflow",
            "'NoneType' object has no attribute 'resolve_component_path'",
            "Error creating class. ModuleNotFoundError",
        ]

        for error in critical_errors:
            assert error not in output, f"Critical error found: {error}\nFull output:\n{output}"

    def test_simple_agent_flow_loads_directly(self, simple_agent_flow_path: Path):
        """Test that Simple Agent flow loads correctly using load_flow_from_json."""
        from lfx.load import load_flow_from_json

        try:
            graph = load_flow_from_json(simple_agent_flow_path, disable_logs=True)
            assert graph is not None, "Graph should not be None"
            assert hasattr(graph, "vertices"), "Graph should have vertices"
            assert len(graph.vertices) > 0, "Graph should have at least one vertex"

            # Prepare the graph
            graph.prepare()

            # Verify Agent component is in the graph
            component_types = {v.display_name for v in graph.vertices if hasattr(v, "display_name")}
            assert "Agent" in component_types or any("Agent" in ct for ct in component_types), (
                f"Expected Agent in graph, found: {component_types}"
            )

        except ModuleNotFoundError as e:
            pytest.fail(f"ModuleNotFoundError loading graph: {e}")
        except Exception as e:
            if "resolve_component_path" in str(e):
                pytest.fail(f"Storage service error: {e}")
            raise

    def test_simple_agent_flow_json_output(self, simple_agent_flow_path: Path):
        """Test that lfx run produces valid JSON output."""
        result = runner.invoke(
            lfx_app,
            ["run", "--format", "json", "--no-check-variables", str(simple_agent_flow_path), "test"],
        )

        # Output should contain valid JSON
        output_json = parse_json_from_output(result.output.strip())
        assert isinstance(output_json, dict), "Output should be a JSON object"


class TestSimpleAgentExecution:
    """Test that Simple Agent flow can actually execute with real API key."""

    @pytest.fixture
    def simple_agent_flow_path(self) -> Path:
        """Get Simple Agent flow path, skip if not found."""
        path = get_simple_agent_flow_path()
        if not path.exists():
            pytest.skip(f"Simple Agent flow not found at {path}")
        return path

    @pytest.mark.skipif(not has_openai_api_key(), reason="OPENAI_API_KEY required")
    def test_simple_agent_executes_successfully(self, simple_agent_flow_path: Path):
        """Test full execution of Simple Agent with real API key.

        This test verifies that the Simple Agent flow executes successfully
        and returns a valid response.
        """
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "lfx",
                "run",
                "--format",
                "json",
                str(simple_agent_flow_path),
                "What is 2 + 2?",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env={**os.environ},
        )

        # Parse output
        output = result.stdout.strip() or result.stderr.strip()
        output_json = parse_json_from_output(output, context=f"stdout: {result.stdout}\nstderr: {result.stderr}")

        # Assert successful execution
        assert output_json.get("success") is True, f"Execution failed: {output_json}"
        assert "result" in output_json, f"No result in output: {output_json}"
        # Verify we got a meaningful response
        result_text = str(output_json.get("result", ""))
        assert len(result_text) > 0, "Result should not be empty"

    @pytest.mark.skipif(not has_openai_api_key(), reason="OPENAI_API_KEY required")
    def test_simple_agent_with_math_question(self, simple_agent_flow_path: Path):
        """Test Simple Agent can use Calculator tool."""
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "lfx",
                "run",
                "--format",
                "json",
                str(simple_agent_flow_path),
                "Calculate 15 multiplied by 7",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env={**os.environ},
        )

        output = result.stdout.strip() or result.stderr.strip()
        output_json = parse_json_from_output(output)

        if output_json.get("success"):
            result_text = str(output_json.get("result", ""))
            # The agent should compute 15 * 7 = 105
            assert "105" in result_text, f"Expected 105 in result: {result_text}"


class TestSimpleAgentServe:
    """Test that Simple Agent can be served."""

    @pytest.fixture
    def simple_agent_flow_path(self) -> Path:
        """Get Simple Agent flow path, skip if not found."""
        path = get_simple_agent_flow_path()
        if not path.exists():
            pytest.skip(f"Simple Agent flow not found at {path}")
        return path

    def test_serve_help(self):
        """Test serve help command works."""
        result = runner.invoke(lfx_app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.output.lower() or "Serve" in result.output

    def test_serve_requires_api_key(self, simple_agent_flow_path: Path, monkeypatch):
        """Test serve requires LANGFLOW_API_KEY."""
        monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)

        result = runner.invoke(
            lfx_app,
            ["serve", str(simple_agent_flow_path)],
        )

        # Should fail or warn about API key
        assert result.exit_code != 0 or "LANGFLOW_API_KEY" in result.output

    def test_serve_loads_flow(self, simple_agent_flow_path: Path):
        """Test serve can load the flow without module errors.

        Note: We test graph loading directly instead of invoking the serve command
        because the serve command now properly starts a server that runs indefinitely.
        """
        from lfx.load import load_flow_from_json

        try:
            graph = load_flow_from_json(simple_agent_flow_path, disable_logs=True)
            assert graph is not None, "Graph should not be None"
            graph.prepare()
        except ModuleNotFoundError as e:
            pytest.fail(f"ModuleNotFoundError loading graph for serve: {e}")
        except Exception as e:
            if "resolve_component_path" in str(e):
                pytest.fail(f"Storage service error: {e}")
            raise

    def test_serve_starts_server_no_asyncio_error(self, simple_agent_flow_path: Path):
        """Regression test: lfx serve should not fail with asyncio error.

        This test verifies the fix for the issue where lfx serve failed with:
        'asyncio.run() cannot be called from a running event loop'

        The fix was to use uvicorn.Server with await server.serve() instead of
        uvicorn.run() which internally calls asyncio.run().
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            test_port = s.getsockname()[1]

        # Start serve in a subprocess with unbuffered output on a specific port
        proc = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-u",  # Unbuffered output
                "-m",
                "lfx",
                "serve",
                "--verbose",
                "--port",
                str(test_port),
                str(simple_agent_flow_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, "LANGFLOW_API_KEY": "test-key-12345"},  # pragma: allowlist secret
        )

        server_ready = False
        output_chunks = []
        timeout = 15  # seconds
        start_time = time.time()
        actual_port = test_port

        try:
            while time.time() - start_time < timeout:
                # Check if process exited
                exit_code = proc.poll()
                if exit_code is not None:
                    # Process exited - read remaining output
                    if proc.stdout:
                        remaining = proc.stdout.read()
                        if remaining:
                            output_chunks.append(remaining)
                    output = "".join(output_chunks)

                    # Check for the specific asyncio errors we're regression testing
                    if "asyncio.run() cannot be called from a running event loop" in output:
                        pytest.fail(f"Regression: lfx serve failed with asyncio error.\nOutput:\n{output}")

                    if "coroutine 'Server.serve' was never awaited" in output:
                        pytest.fail(f"Regression: Server.serve coroutine was never awaited.\nOutput:\n{output}")

                    # Process exited for another reason
                    pytest.fail(f"Server process exited with code {exit_code}.\nOutput:\n{output}")

                # Try to read available output without blocking (Unix only)
                if proc.stdout:
                    try:
                        ready, _, _ = select.select([proc.stdout], [], [], 0.1)
                        if ready:
                            chunk = proc.stdout.readline()
                            if chunk:
                                output_chunks.append(chunk)
                                # Check if server switched to a different port
                                if "using port" in chunk.lower():
                                    port_match = re.search(r"port (\d+)", chunk)
                                    if port_match:
                                        actual_port = int(port_match.group(1))
                    except (ValueError, OSError):
                        pass

                # Try to connect to server on actual port
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{actual_port}/docs", timeout=1)
                    server_ready = True
                    break
                except Exception:
                    time.sleep(0.3)

            if not server_ready:
                output = "".join(output_chunks)
                pytest.fail(f"Server did not become ready within {timeout}s.\nOutput:\n{output}")

        finally:
            # Clean up - terminate the server
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


class TestAllStarterProjectsLoad:
    """Test that all starter projects can load without lfx-specific module errors."""

    @pytest.fixture
    def starter_projects_path(self) -> Path:
        """Get starter projects path."""
        path = get_starter_projects_path()
        if not path.exists():
            pytest.skip(f"Starter projects not found at {path}")
        return path

    def test_all_projects_load(self, starter_projects_path: Path):
        """Test all starter project JSONs can load without lfx-specific errors.

        Note: This test only fails on lfx-specific module errors (lfx.components.*),
        not on missing external dependencies (langchain_anthropic, etc.) which are
        expected when running with minimal dev dependencies.
        """
        from lfx.load import load_flow_from_json

        json_files = list(starter_projects_path.glob("*.json"))
        assert len(json_files) > 0, "No starter project files found"

        lfx_module_errors = []

        for json_file in json_files:
            try:
                graph = load_flow_from_json(json_file, disable_logs=True)
                assert graph is not None
                graph.prepare()
            except Exception as e:
                error_str = str(e)
                # Only track lfx-specific errors, not external dependency errors
                if "No module named 'lfx." in error_str:
                    lfx_module_errors.append((json_file.name, str(e)))
                elif "resolve_component_path" in error_str:
                    lfx_module_errors.append((json_file.name, f"Storage error: {e}"))
                # External dependency errors (langchain_anthropic, etc.) are acceptable
                # as lfx is designed to work with minimal dependencies

        if lfx_module_errors:
            error_details = "\n".join([f"  {name}: {error}" for name, error in lfx_module_errors])
            pytest.fail(f"LFX module errors in starter projects:\n{error_details}")
