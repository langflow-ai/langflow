"""Common utilities for CLI commands."""

from __future__ import annotations

import ast
import contextlib
import importlib.metadata as importlib_metadata
import io
import os
import re
import socket
import subprocess
import sys
import tempfile
import uuid
import zipfile
from io import StringIO
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
import typer

from langflow.api.v1.schemas import InputValueRequest
from langflow.cli.script_loader import (
    extract_structured_result,
    find_graph_variable,
    load_graph_from_script,
)
from langflow.load import load_flow_from_json

if TYPE_CHECKING:
    from types import ModuleType

# Attempt to import tomllib (3.11+) else fall back to tomli
_toml_parser: ModuleType | None = None
try:
    import tomllib as _toml_parser
except ModuleNotFoundError:
    with contextlib.suppress(ModuleNotFoundError):
        import tomli as toml_parser

        _toml_parser = toml_parser

MAX_PORT_NUMBER = 65535

# Fixed namespace constant for deterministic UUID5 generation across runs
_LANGFLOW_NAMESPACE_UUID = uuid.UUID("3c091057-e799-4e32-8ebc-27bc31e1108c")

# Environment variable for GitHub token
_GITHUB_TOKEN_ENV = "GITHUB_TOKEN"  # noqa: S105


def create_verbose_printer(*, verbose: bool):
    """Create a verbose printer function that only prints in verbose mode.

    Args:
        verbose: Whether to print verbose output

    Returns:
        Function that prints to stderr only in verbose mode
    """

    def verbose_print(message: str) -> None:
        """Print diagnostic messages to stderr only in verbose mode."""
        if verbose:
            typer.echo(message, file=sys.stderr)

    return verbose_print


def is_port_in_use(port: int, host: str = "localhost") -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return True
        else:
            return False


def get_free_port(starting_port: int = 8000) -> int:
    """Get a free port starting from the given port."""
    port = starting_port
    while port < MAX_PORT_NUMBER:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
            except OSError:
                port += 1
            else:
                return port
    msg = "No free ports available"
    raise RuntimeError(msg)


def get_best_access_host(host: str) -> str:
    """Get the best host address for external access."""
    # Note: 0.0.0.0 and :: are intentionally checked as they bind to all interfaces
    if host in ("0.0.0.0", "::"):  # noqa: S104
        return "localhost"
    return host


def get_api_key() -> str:
    """Get the API key from environment variable."""
    api_key = os.getenv("LANGFLOW_API_KEY")
    if not api_key:
        msg = "LANGFLOW_API_KEY environment variable is required"
        raise ValueError(msg)
    return api_key


def is_url(path_or_url: str) -> bool:
    """Check if the given string is a URL.

    Args:
        path_or_url: String to check

    Returns:
        True if it's a URL, False otherwise
    """
    try:
        result = urlparse(path_or_url)
        return all([result.scheme, result.netloc])
    except Exception:  # noqa: BLE001
        return False


def download_script_from_url(url: str, verbose_print) -> Path:
    """Download a Python script from a URL and save it to a temporary file.

    Args:
        url: URL to download the script from
        verbose_print: Function to print verbose messages

    Returns:
        Path to the temporary file containing the downloaded script

    Raises:
        typer.Exit: If download fails
    """
    verbose_print(f"Downloading script from URL: {url}")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()

            # Check if the response is a Python script
            content_type = response.headers.get("content-type", "").lower()
            valid_types = {"application/x-python", "application/octet-stream"}
            if not (content_type.startswith("text/") or content_type in valid_types):
                verbose_print(f"Warning: Unexpected content type: {content_type}")

            # Create a temporary file with .py extension
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
                temp_path = Path(temp_file.name)

                # Write the content to the temporary file
                script_content = response.text
                temp_file.write(script_content)

            verbose_print(f"✓ Script downloaded successfully to temporary file: {temp_path}")
            return temp_path

    except httpx.HTTPStatusError as e:
        msg = f"✗ HTTP error downloading script: {e.response.status_code} - {e.response.text}"
        verbose_print(msg)
        raise typer.Exit(1) from e
    except httpx.RequestError as e:
        msg = f"✗ Network error downloading script: {e}"
        verbose_print(msg)
        raise typer.Exit(1) from e
    except Exception as e:
        msg = f"✗ Unexpected error downloading script: {e}"
        verbose_print(msg)
        raise typer.Exit(1) from e


def validate_script_path(script_path: Path | str, verbose_print) -> tuple[str, Path]:
    """Validate script path or URL and return file extension and resolved path.

    Args:
        script_path: Path to the script file or URL
        verbose_print: Function to print verbose messages

    Returns:
        Tuple of (file_extension, resolved_path)

    Raises:
        typer.Exit: If validation fails
    """
    # Handle URL case
    if isinstance(script_path, str) and is_url(script_path):
        resolved_path = download_script_from_url(script_path, verbose_print)
        file_extension = resolved_path.suffix.lower()
        if file_extension != ".py":
            verbose_print(f"Error: URL must point to a Python script (.py file), got: {file_extension}")
            raise typer.Exit(1)
        return file_extension, resolved_path

    # Handle local file case
    if isinstance(script_path, str):
        script_path = Path(script_path)

    if not script_path.exists():
        verbose_print(f"Error: File '{script_path}' does not exist.")
        raise typer.Exit(1)

    if not script_path.is_file():
        verbose_print(f"Error: '{script_path}' is not a file.")
        raise typer.Exit(1)

    # Check file extension and validate
    file_extension = script_path.suffix.lower()
    if file_extension not in [".py", ".json"]:
        verbose_print(f"Error: '{script_path}' must be a .py or .json file.")
        raise typer.Exit(1)

    return file_extension, script_path


def load_graph_from_path(script_path: Path, file_extension: str, verbose_print, *, verbose: bool = False):
    """Load a graph from a Python script or JSON file.

    Args:
        script_path: Path to the script file
        file_extension: File extension (.py or .json)
        verbose_print: Function to print verbose messages
        verbose: Whether verbose mode is enabled

    Returns:
        Loaded graph object

    Raises:
        typer.Exit: If loading fails
    """
    file_type = "Python script" if file_extension == ".py" else "JSON flow"
    verbose_print(f"Analyzing {file_type}: {script_path}")

    try:
        if file_extension == ".py":
            verbose_print("Analyzing Python script...")
            graph_var = find_graph_variable(script_path)
            if graph_var:
                source_info = graph_var.get("source", "Unknown")
                type_info = graph_var.get("type", "Unknown")
                line_no = graph_var.get("line", "Unknown")
                verbose_print(f"✓ Found 'graph' variable at line {line_no}")
                verbose_print(f"  Type: {type_info}")
                verbose_print(f"  Source: {source_info}")
            else:
                error_msg = "No 'graph' variable found in script"
                verbose_print(f"✗ {error_msg}")
                raise ValueError(error_msg)

            verbose_print("Loading graph...")
            graph = load_graph_from_script(script_path)
        else:  # .json
            verbose_print("Loading JSON flow...")
            graph = load_flow_from_json(script_path, disable_logs=not verbose)

    except ValueError as e:
        # Re-raise ValueError as typer.Exit to preserve the error message
        raise typer.Exit(1) from e
    except Exception as e:
        verbose_print(f"✗ Failed to load graph: {e}")
        raise typer.Exit(1) from e
    else:
        return graph


def prepare_graph(graph, verbose_print):
    """Prepare a graph for execution.

    Args:
        graph: Graph object to prepare
        verbose_print: Function to print verbose messages

    Raises:
        typer.Exit: If preparation fails
    """
    verbose_print("Preparing graph for execution...")
    try:
        graph.prepare()
        verbose_print("✓ Graph prepared successfully")
    except Exception as e:
        verbose_print(f"✗ Failed to prepare graph: {e}")
        raise typer.Exit(1) from e


async def execute_graph_with_capture(graph, input_value: str | None):
    """Execute a graph and capture output.

    Args:
        graph: Graph object to execute
        input_value: Input value to pass to the graph

    Returns:
        Tuple of (results, captured_logs)

    Raises:
        Exception: Re-raises any exception that occurs during graph execution
    """
    # Create input request
    inputs = InputValueRequest(input_value=input_value) if input_value else None

    # Capture output during execution
    captured_stdout = StringIO()
    captured_stderr = StringIO()

    # Redirect stdout and stderr during graph execution
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr
        results = [result async for result in graph.async_start(inputs)]
    except Exception as exc:
        # Capture any error output that was written to stderr
        error_output = captured_stderr.getvalue()
        if error_output:
            # Add error output to the exception for better debugging
            exc.args = (f"{exc.args[0] if exc.args else str(exc)}\n\nCaptured stderr:\n{error_output}",)
        raise
    finally:
        # Restore original stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    # Get captured logs
    captured_logs = captured_stdout.getvalue() + captured_stderr.getvalue()

    return results, captured_logs


def extract_result_data(results, captured_logs: str) -> dict:
    """Extract structured result data from graph execution results.

    Args:
        results: Graph execution results
        captured_logs: Captured output logs

    Returns:
        Structured result data dictionary
    """
    result_data = extract_structured_result(results)
    result_data["logs"] = captured_logs
    return result_data


# --- Dependency helpers ------------------------------------------------------------------


def _parse_pep723_block(script_path: Path, verbose_print) -> dict | None:
    """Extract the TOML table contained in a PEP-723 inline metadata block.

    Args:
        script_path: Path to the Python script to inspect.
        verbose_print: Diagnostic printer.

    Returns:
        Parsed TOML dict if a block is found and successfully parsed, otherwise None.
    """
    if _toml_parser is None:
        verbose_print("tomllib/tomli not available - cannot parse inline dependencies")
        return None

    try:
        lines = script_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:  # pragma: no cover
        verbose_print(f"Failed reading script for dependency parsing: {exc}")
        return None

    # Locate `# /// script` and closing `# ///` markers.
    try:
        start_idx = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("# /// script")) + 1
        end_idx = next(i for i, ln in enumerate(lines[start_idx:], start=start_idx) if ln.lstrip().startswith("# ///"))
    except StopIteration:
        return None  # No valid block

    # Remove leading comment markers and excess whitespace
    block_lines: list[str] = []
    for raw_line in lines[start_idx:end_idx]:
        stripped_line = raw_line.lstrip()
        if not stripped_line.startswith("#"):
            continue
        block_lines.append(stripped_line.lstrip("# "))

    block_toml = "\n".join(block_lines).strip()
    if not block_toml:
        return None

    try:
        return _toml_parser.loads(block_toml)
    except Exception as exc:  # pragma: no cover  # noqa: BLE001
        verbose_print(f"Failed parsing TOML from PEP-723 block: {exc}")
        return None


def extract_script_dependencies(script_path: Path, verbose_print) -> list[str]:
    """Return dependency strings declared via PEP-723 inline metadata.

    Only `.py` files are supported for now. Returns an empty list if the file has
    no metadata block or could not be parsed.
    """
    if script_path.suffix != ".py":
        return []

    parsed = _parse_pep723_block(script_path, verbose_print)
    if not parsed:
        return []

    deps = parsed.get("dependencies", [])
    # Ensure list[str]
    if isinstance(deps, list):
        return [str(d).strip() for d in deps if str(d).strip()]
    return []


def _needs_install(requirement: str) -> bool:
    """Heuristic: check if *some* distribution that satisfies the requirement is present.

    Exact version resolution is delegated to the installer; here we do a best-effort
    importlib.metadata lookup for the top-level name before the first comparison op.
    """
    from packaging.requirements import Requirement  # locally imported to avoid hard dep if unused

    try:
        req = Requirement(requirement)
    except Exception:  # noqa: BLE001
        return True  # If we cannot parse it, assume missing so installer handles it

    try:
        dist_version = importlib_metadata.version(req.name)
    except importlib_metadata.PackageNotFoundError:
        return True

    # If specifier is empty, we already have it.
    if not req.specifier:
        return False

    try:
        from packaging.version import InvalidVersion, Version
    except ImportError:
        # If packaging is missing, we cannot compare - treat as missing.
        return True

    try:
        if req.specifier.contains(Version(dist_version), prereleases=True):
            return False
    except InvalidVersion:
        return True

    return True


def ensure_dependencies_installed(dependencies: list[str], verbose_print) -> None:
    """Install missing dependencies using uv (preferred) or pip.

    Args:
        dependencies: List of requirement strings (PEP 508 style).
        verbose_print: Diagnostic printer.
    """
    if not dependencies:
        return

    missing = [req for req in dependencies if _needs_install(req)]
    if not missing:
        verbose_print("All script dependencies already satisfied")
        return

    installer_cmd: list[str]
    if which("uv"):
        installer_cmd = ["uv", "pip", "install", "--quiet", *missing]
        tool_name = "uv"
    else:
        # Fall back to current interpreter's pip
        installer_cmd = [sys.executable, "-m", "pip", "install", "--quiet", *missing]
        tool_name = "pip"

    verbose_print(f"Installing missing dependencies with {tool_name}: {', '.join(missing)}")
    try:
        subprocess.run(installer_cmd, check=True)  # noqa: S603
        verbose_print("✓ Dependency installation succeeded")
    except subprocess.CalledProcessError as exc:  # pragma: no cover
        verbose_print(f"✗ Failed installing dependencies: {exc}")
        raise typer.Exit(1) from exc


def flow_id_from_path(file_path: Path, root_dir: Path) -> str:
    """Generate a deterministic UUID-5 based flow id from *file_path*.

    The function uses a fixed namespace UUID and the POSIX-style relative path
    (relative to *root_dir*) as the *name* when calling :pyfunc:`uuid.uuid5`.
    This guarantees:

    1.  The same folder deployed again produces identical flow IDs.
    2.  IDs remain stable even if the absolute location of the folder changes
        (only the relative path is hashed).
    3.  Practically collision-free identifiers without maintaining external
        state.

    Args:
        file_path: Path of the JSON flow file.
        root_dir: Root directory from which *file_path* should be considered
            relative.  Typically the folder passed to the deploy command.

    Returns:
    -------
    str
        Canonical UUID string (36 chars, including hyphens).
    """
    relative = file_path.relative_to(root_dir).as_posix()
    return str(uuid.uuid5(_LANGFLOW_NAMESPACE_UUID, relative))


# ---------------------------------------------------------------------------
# GitHub / ZIP repository helpers (synchronous equivalents of initial_setup)
# ---------------------------------------------------------------------------

_GITHUB_RE_REPO = re.compile(r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)(?:\.git)?/?$")
_GITHUB_RE_TREE = re.compile(r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/tree/([\w\/-]+)")
_GITHUB_RE_RELEASE = re.compile(r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/releases/tag/([\w\/-]+)")
_GITHUB_RE_COMMIT = re.compile(r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/commit/(\w+)(?:/)?$")


def _github_headers() -> dict[str, str]:
    token = os.getenv(_GITHUB_TOKEN_ENV)
    if token:
        return {"Authorization": f"token {token}"}
    return {}


def detect_github_url_sync(url: str, *, timeout: float = 15.0) -> str:
    """Convert various GitHub URLs into a direct `.zip` download link (sync).

    Mirrors the async implementation in *initial_setup.setup.detect_github_url*.
    """
    if match := _GITHUB_RE_REPO.match(url):
        owner, repo = match.groups()
        # Determine default branch via GitHub API
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=_github_headers()) as client:
            resp = client.get(f"https://api.github.com/repos/{owner}/{repo}")
            resp.raise_for_status()
            default_branch = resp.json().get("default_branch", "main")
        return f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"

    if match := _GITHUB_RE_TREE.match(url):
        owner, repo, branch = match.groups()
        branch = branch.rstrip("/")
        return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"

    if match := _GITHUB_RE_RELEASE.match(url):
        owner, repo, tag = match.groups()
        tag = tag.rstrip("/")
        return f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.zip"

    if match := _GITHUB_RE_COMMIT.match(url):
        owner, repo, commit = match.groups()
        return f"https://github.com/{owner}/{repo}/archive/{commit}.zip"

    # Not a recognized GitHub URL; assume it's already a direct link
    return url


def download_and_extract_repo(url: str, verbose_print, *, timeout: float = 60.0) -> Path:
    """Download a ZIP archive from *url* and extract into a temp directory.

    Returns the **root directory** containing the extracted files.
    """
    verbose_print(f"Downloading repository/ZIP from {url}")

    zip_url = detect_github_url_sync(url)

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=_github_headers()) as client:
            resp = client.get(zip_url)
            resp.raise_for_status()

        tmp_dir = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extractall(tmp_dir.name)

        verbose_print(f"✓ Repository extracted to {tmp_dir.name}")

        # Most GitHub archives have a single top-level folder; use it if present
        root_path = Path(tmp_dir.name)
        sub_entries = list(root_path.iterdir())
        if len(sub_entries) == 1 and sub_entries[0].is_dir():
            root_path = sub_entries[0]

        # Ensure root on sys.path for custom components
        if str(root_path) not in sys.path:
            sys.path.insert(0, str(root_path))

        # Attach TemporaryDirectory to path object so caller can keep reference
        # and prevent premature cleanup. We set attribute _tmp_dir.
        root_path._tmp_dir = tmp_dir  # type: ignore[attr-defined]

    except httpx.HTTPStatusError as e:
        verbose_print(f"✗ HTTP error downloading ZIP: {e.response.status_code}")
        raise
    except Exception as exc:
        verbose_print(f"✗ Failed downloading or extracting repo: {exc}")
        raise
    else:
        return root_path


def extract_script_docstring(script_path: Path) -> str | None:
    """Extract the module-level docstring from a Python script.

    Args:
        script_path: Path to the Python script file

    Returns:
        The docstring text if found, None otherwise
    """
    try:
        # Read the file content
        with script_path.open(encoding="utf-8") as f:
            content = f.read()

        # Parse the AST
        tree = ast.parse(content)

        # Check if the first statement is a docstring
        # A docstring is a string literal that appears as the first statement
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            docstring = tree.body[0].value.value
            # Clean up the docstring by removing extra whitespace
            return docstring.strip()

    except (OSError, SyntaxError, UnicodeDecodeError):
        # If we can't read or parse the file, just return None
        # Don't raise an error as this is optional functionality
        pass

    return None
