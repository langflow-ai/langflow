"""Script loading utilities for Langflow CLI.

This module provides functionality to load and validate Python scripts
containing Langflow graph variables.
"""

import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langflow.graph.graph.base import Graph
    from langflow.schema.message import Message


@contextmanager
def temporary_sys_path(path: str):
    """Temporarily add a path to sys.path."""
    if path not in sys.path:
        sys.path.insert(0, path)
        try:
            yield
        finally:
            sys.path.remove(path)
    else:
        yield


def _load_module_from_script(script_path: Path) -> Any:
    """Load a Python module from a script file."""
    spec = importlib.util.spec_from_file_location("script_module", script_path)
    if spec is None or spec.loader is None:
        msg = f"Could not create module spec for '{script_path}'"
        raise ImportError(msg)

    module = importlib.util.module_from_spec(spec)

    with temporary_sys_path(str(script_path.parent)):
        spec.loader.exec_module(module)

    return module


def _validate_graph_instance(graph_obj: "Graph"):
    """Extract information from a graph object."""
    from langflow.graph.graph.base import Graph

    if not isinstance(graph_obj, Graph):
        msg = f"Graph object is not a Langflow Graph instance: {type(graph_obj)}"
        raise TypeError(msg)

    # Find ChatInput and ChatOutput components
    display_names = {vertex.custom_component.display_name for vertex in graph_obj.vertices}

    if "Chat Input" not in display_names:
        msg = f"Graph does not contain any ChatInput component. Vertices: {display_names}"
        raise ValueError(msg)

    if "Chat Output" not in display_names:
        msg = f"Graph does not contain any ChatOutput component. Vertices: {display_names}"
        raise ValueError(msg)

    return graph_obj


def load_graph_from_script(script_path: Path) -> "Graph":
    """Load and execute a Python script to extract the 'graph' variable.

    Args:
        script_path (Path): Path to the Python script file

    Returns:
        dict: Information about the loaded graph variable including the graph object itself
    """
    try:
        # Load the module
        module = _load_module_from_script(script_path)

        # Check if 'graph' variable exists
        if not hasattr(module, "graph"):
            return {"success": False, "error": "No 'graph' variable found in the executed script"}

        # Extract graph information
        graph_obj = module.graph
        return _validate_graph_instance(graph_obj)

    except (ImportError, AttributeError, ModuleNotFoundError, SyntaxError, TypeError, ValueError) as e:
        error_msg = f"Error executing script '{script_path}': {e}"
        raise RuntimeError(error_msg) from e


def extract_message_from_result(results: list) -> str:
    """Extract the message from the results."""
    for result in results:
        if hasattr(result, "vertex") and result.vertex.custom_component.display_name == "Chat Output":
            message: Message = result.result_dict.results["message"]
            try:
                # Parse the JSON to get just the text content
                return message.model_dump_json()
            except (json.JSONDecodeError, AttributeError):
                # Fallback to string representation
                return str(message)
    return "No response generated"
