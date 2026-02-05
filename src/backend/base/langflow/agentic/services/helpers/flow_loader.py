"""Flow loading utilities.

Supports loading graphs from both Python (.py) and JSON (.json) flow files.
When both exist, .py takes priority for gradual migration.
"""

import importlib.util
import inspect
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException
from lfx.load import aload_flow_from_json
from lfx.log.logger import logger

from langflow.agentic.services.flow_preparation import load_and_prepare_flow
from langflow.agentic.services.flow_types import FLOWS_BASE_PATH

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph


@contextmanager
def _temporary_sys_path(path: str):
    """Temporarily add a path to sys.path."""
    if path not in sys.path:
        sys.path.insert(0, path)
        try:
            yield
        finally:
            sys.path.remove(path)
    else:
        yield


def _validate_path_within_base(candidate: Path, flow_filename: str) -> Path:
    """Validate that a path is within FLOWS_BASE_PATH to prevent path traversal.

    Args:
        candidate: The candidate path to validate.
        flow_filename: Original filename for error messages.

    Returns:
        The resolved path if valid.

    Raises:
        HTTPException: If path is outside FLOWS_BASE_PATH (path traversal attempt).
    """
    base_path = FLOWS_BASE_PATH.resolve()
    resolved = candidate.resolve()

    # Check if resolved path is within base path
    try:
        resolved.relative_to(base_path)
    except ValueError:
        # Path is outside base directory - potential path traversal
        raise HTTPException(status_code=400, detail=f"Invalid flow path: '{flow_filename}'") from None

    return resolved


def resolve_flow_path(flow_filename: str) -> tuple[Path, str]:
    """Resolve flow filename to path and determine type.

    Supports both explicit extensions (.json, .py) and auto-detection.
    Priority: explicit extension > .py > .json

    Args:
        flow_filename: Name of the flow file (with or without extension).

    Returns:
        tuple[Path, str]: (resolved path, file type: "json" or "python")

    Raises:
        HTTPException: If flow file not found or path traversal detected.
    """
    if flow_filename.endswith(".json"):
        flow_path = _validate_path_within_base(FLOWS_BASE_PATH / flow_filename, flow_filename)
        if flow_path.exists():
            return flow_path, "json"
        raise HTTPException(status_code=404, detail=f"Flow file '{flow_filename}' not found")

    if flow_filename.endswith(".py"):
        flow_path = _validate_path_within_base(FLOWS_BASE_PATH / flow_filename, flow_filename)
        if flow_path.exists():
            return flow_path, "python"
        raise HTTPException(status_code=404, detail=f"Flow file '{flow_filename}' not found")

    # Auto-detect: try Python first, then JSON (allows gradual migration)
    base_name = flow_filename.rsplit(".", 1)[0] if "." in flow_filename else flow_filename

    py_path = _validate_path_within_base(FLOWS_BASE_PATH / f"{base_name}.py", flow_filename)
    if py_path.exists():
        return py_path, "python"

    json_path = _validate_path_within_base(FLOWS_BASE_PATH / f"{base_name}.json", flow_filename)
    if json_path.exists():
        return json_path, "json"

    # Try without adding extension
    direct_path = _validate_path_within_base(FLOWS_BASE_PATH / flow_filename, flow_filename)
    if direct_path.exists():
        if direct_path.suffix == ".py":
            return direct_path, "python"
        return direct_path, "json"

    raise HTTPException(status_code=404, detail=f"Flow file '{flow_filename}' not found")


async def _load_graph_from_python(
    flow_path: Path,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> "Graph":
    """Load a Graph from a Python flow file.

    The Python file must define a function `get_graph()` that returns a Graph.
    The function can optionally accept provider, model_name, and api_key_var parameters.

    Args:
        flow_path: Path to the Python flow file.
        provider: Optional model provider (e.g., "OpenAI").
        model_name: Optional model name (e.g., "gpt-4o-mini").
        api_key_var: Optional API key variable name.

    Returns:
        Graph: The loaded and configured graph.

    Raises:
        HTTPException: If the flow file cannot be loaded or executed.
    """
    module_name = flow_path.stem
    spec = importlib.util.spec_from_file_location(module_name, flow_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=500, detail=f"Could not load flow module: {flow_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        with _temporary_sys_path(str(flow_path.parent)):
            spec.loader.exec_module(module)
    except Exception as e:
        if module_name in sys.modules:
            del sys.modules[module_name]
        logger.error(f"Error loading Python flow module: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading flow module: {e}") from e

    if not hasattr(module, "get_graph"):
        # Fallback: check for 'graph' variable for backward compatibility
        if hasattr(module, "graph"):
            graph = module.graph
            if module_name in sys.modules:
                del sys.modules[module_name]
            return graph
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise HTTPException(status_code=500, detail=f"Flow module must define 'get_graph()' function: {flow_path}")

    get_graph_func = module.get_graph

    # Build kwargs for get_graph based on what it accepts
    sig = inspect.signature(get_graph_func)
    kwargs = {}
    if "provider" in sig.parameters and provider:
        kwargs["provider"] = provider
    if "model_name" in sig.parameters and model_name:
        kwargs["model_name"] = model_name
    if "api_key_var" in sig.parameters and api_key_var:
        kwargs["api_key_var"] = api_key_var

    try:
        if inspect.iscoroutinefunction(get_graph_func):
            graph = await get_graph_func(**kwargs)
        else:
            graph = get_graph_func(**kwargs)
    except Exception as e:
        logger.error(f"Error executing get_graph(): {e}")
        raise HTTPException(status_code=500, detail=f"Error creating graph: {e}") from e
    finally:
        if module_name in sys.modules:
            del sys.modules[module_name]

    return graph


async def load_graph_for_execution(
    flow_path: Path,
    flow_type: str,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> "Graph":
    """Load graph from either Python or JSON flow.

    Args:
        flow_path: Path to the flow file.
        flow_type: Either "python" or "json".
        provider: Model provider for injection.
        model_name: Model name for injection.
        api_key_var: API key variable name.

    Returns:
        Graph: Ready-to-execute graph instance.
    """
    if flow_type == "python":
        return await _load_graph_from_python(flow_path, provider, model_name, api_key_var)

    # JSON flow: use existing load_and_prepare_flow for model injection
    flow_json = load_and_prepare_flow(flow_path, provider, model_name, api_key_var)
    flow_dict = json.loads(flow_json)
    return await aload_flow_from_json(flow_dict, disable_logs=True)
