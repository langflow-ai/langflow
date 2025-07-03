"""Common utilities for CLI commands."""

import contextlib
import importlib.metadata as importlib_metadata
import subprocess
import sys
from io import StringIO
from pathlib import Path
from shutil import which
from types import ModuleType

import typer

from langflow.api.v1.schemas import InputValueRequest
from langflow.cli.script_loader import (
    extract_structured_result,
    find_graph_variable,
    load_graph_from_script,
)
from langflow.load import load_flow_from_json

# Attempt to import tomllib (3.11+) else fall back to tomli
_toml_parser: ModuleType | None = None
try:
    import tomllib as _toml_parser
except ModuleNotFoundError:
    with contextlib.suppress(ModuleNotFoundError):
        import tomli as toml_parser

        _toml_parser = toml_parser


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


def validate_script_path(script_path: Path, verbose_print) -> str:
    """Validate script path and return file extension.

    Args:
        script_path: Path to the script file
        verbose_print: Function to print verbose messages

    Returns:
        File extension (.py or .json)

    Raises:
        typer.Exit: If validation fails
    """
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

    return file_extension


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


def execute_graph_with_capture(graph, input_value: str | None):
    """Execute a graph and capture output.

    Args:
        graph: Graph object to execute
        input_value: Input value to pass to the graph

    Returns:
        Tuple of (results, captured_logs)
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
        results = list(graph.start(inputs))
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
