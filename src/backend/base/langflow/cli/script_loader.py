"""Script loading utilities for Langflow CLI.

This module provides functionality to load and validate Python scripts
containing Langflow graph variables.
"""

import ast
import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

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


def _validate_graph_instance(graph_obj: Any) -> "Graph":
    """Extract information from a graph object."""
    from langflow.graph.graph.base import Graph

    if not isinstance(graph_obj, Graph):
        msg = f"Graph object is not a Langflow Graph instance: {type(graph_obj)}"
        raise TypeError(msg)

    # Find ChatInput and ChatOutput components
    display_names: set[str] = set()
    for vertex in graph_obj.vertices:
        if vertex.custom_component is not None:
            display_names.add(vertex.custom_component.display_name)

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
            msg = "No 'graph' variable found in the executed script"
            raise ValueError(msg)

        # Extract graph information
        graph_obj = module.graph
        return _validate_graph_instance(graph_obj)

    except (ImportError, AttributeError, ModuleNotFoundError, SyntaxError, TypeError, ValueError) as e:
        error_msg = f"Error executing script '{script_path}': {e}"
        raise RuntimeError(error_msg) from e


def extract_message_from_result(results: list) -> str:
    """Extract the message from the results."""
    for result in results:
        if (
            hasattr(result, "vertex")
            and result.vertex.custom_component
            and result.vertex.custom_component.display_name == "Chat Output"
        ):
            message: Message = result.result_dict.results["message"]
            try:
                # Parse the JSON to get just the text content
                return message.model_dump_json()
            except (json.JSONDecodeError, AttributeError):
                # Fallback to string representation
                return str(message)
    return "No response generated"


def extract_text_from_result(results: list) -> str:
    """Extract just the text content from the results."""
    for result in results:
        if (
            hasattr(result, "vertex")
            and result.vertex.custom_component
            and result.vertex.custom_component.display_name == "Chat Output"
        ):
            message: Message = result.result_dict.results["message"]
            try:
                # Return just the text content
                text_content = message.text if hasattr(message, "text") else str(message)
                return str(text_content)
            except AttributeError:
                # Fallback to string representation
                return str(message)
    return "No response generated"


def extract_structured_result(results: list, *, extract_text: bool = True) -> dict:
    """Extract structured result data from the results."""
    for result in results:
        if (
            hasattr(result, "vertex")
            and result.vertex.custom_component
            and result.vertex.custom_component.display_name == "Chat Output"
        ):
            message: Message = result.result_dict.results["message"]
            try:
                result_message = message.text if extract_text and hasattr(message, "text") else message
            except (AttributeError, TypeError, ValueError) as e:
                return {
                    "text": str(message),
                    "type": "message",
                    "component": result.vertex.custom_component.display_name,
                    "component_id": result.vertex.id,
                    "success": True,
                    "warning": f"Could not extract text properly: {e}",
                }

            return {
                "result": result_message,
                "type": "message",
                "component": result.vertex.custom_component.display_name,
                "component_id": result.vertex.id,
                "success": True,
            }
    return {"text": "No response generated", "type": "error", "success": False}


def find_graph_variable(script_path: Path) -> dict | None:
    """Parse a Python script and find the 'graph' variable assignment.

    Args:
        script_path (Path): Path to the Python script file

    Returns:
        dict | None: Information about the graph variable if found, None otherwise
    """
    try:
        with script_path.open(encoding="utf-8") as f:
            content = f.read()

        # Parse the script using AST
        tree = ast.parse(content)

        # Look for assignments to 'graph' variable
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Check if any target is named 'graph'
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "graph":
                        # Found a graph assignment
                        line_number = node.lineno

                        # Try to extract some information about the assignment
                        if isinstance(node.value, ast.Call):
                            # It's a function call like Graph(...)
                            if isinstance(node.value.func, ast.Name):
                                func_name = node.value.func.id
                            elif isinstance(node.value.func, ast.Attribute):
                                # Handle cases like Graph.from_payload(...)
                                if isinstance(node.value.func.value, ast.Name):
                                    func_name = f"{node.value.func.value.id}.{node.value.func.attr}"
                                else:
                                    func_name = node.value.func.attr
                            else:
                                func_name = "Unknown"

                            # Count arguments
                            arg_count = len(node.value.args) + len(node.value.keywords)

                            return {
                                "line_number": line_number,
                                "type": "function_call",
                                "function": func_name,
                                "arg_count": arg_count,
                                "source_line": content.split("\n")[line_number - 1].strip(),
                            }
                        # Some other type of assignment
                        return {
                            "line_number": line_number,
                            "type": "assignment",
                            "source_line": content.split("\n")[line_number - 1].strip(),
                        }

    except FileNotFoundError:
        typer.echo(f"Error: File '{script_path}' not found.")
        return None
    except SyntaxError as e:
        typer.echo(f"Error: Invalid Python syntax in '{script_path}': {e}")
        return None
    except (OSError, UnicodeDecodeError) as e:
        typer.echo(f"Error parsing '{script_path}': {e}")
        return None
    else:
        # No graph variable found
        return None
