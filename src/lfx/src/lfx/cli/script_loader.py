"""Script loading utilities for LFX CLI.

This module provides functionality to load and validate Python scripts
containing LFX graph variables.
"""

import ast
import importlib.util
import inspect
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from lfx.graph import Graph

if TYPE_CHECKING:
    from lfx.schema.message import Message


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


def _validate_graph_instance(graph_obj: Any) -> Graph:
    """Extract information from a graph object."""
    if not isinstance(graph_obj, Graph):
        msg = f"Graph object is not a LFX Graph instance: {type(graph_obj)}"
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


async def load_graph_from_script(script_path: Path) -> Graph:
    """Load and execute a Python script to extract the 'graph' variable or call 'get_graph' function.

    Args:
        script_path (Path): Path to the Python script file

    Returns:
        Graph: The loaded and validated graph instance
    """
    try:
        # Load the module
        module = _load_module_from_script(script_path)

        graph_obj = None

        # First, try to get graph from 'get_graph' function (preferred for async code)
        if hasattr(module, "get_graph") and callable(module.get_graph):
            get_graph_func = module.get_graph

            # Check if get_graph is async and handle accordingly
            if inspect.iscoroutinefunction(get_graph_func):
                graph_obj = await get_graph_func()
            else:
                graph_obj = get_graph_func()

        # Fallback to 'graph' variable for backward compatibility
        elif hasattr(module, "graph"):
            graph_obj = module.graph

        if graph_obj is None:
            msg = "No 'graph' variable or 'get_graph()' function found in the executed script"
            raise ValueError(msg)

        return _validate_graph_instance(graph_obj)

    except (
        ImportError,
        AttributeError,
        ModuleNotFoundError,
        SyntaxError,
        TypeError,
        ValueError,
        FileNotFoundError,
    ) as e:
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
                return json.dumps(json.loads(message.model_dump_json()), ensure_ascii=False)
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
            message: dict | Message = result.result_dict.results.get("message")
            try:
                # Return just the text content
                if isinstance(message, dict):
                    text_content = message.get("text") if message.get("text") else str(message)
                else:
                    text_content = message.text
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
    """Parse a Python script and find the 'graph' variable assignment or 'get_graph' function.

    Args:
        script_path (Path): Path to the Python script file

    Returns:
        dict | None: Information about the graph variable or get_graph function if found, None otherwise
    """
    try:
        with script_path.open(encoding="utf-8") as f:
            content = f.read()

        # Parse the script using AST
        tree = ast.parse(content)

        # Look for 'get_graph' function definitions (preferred) or 'graph' variable assignments
        for node in ast.walk(tree):
            # Check for get_graph function definition
            if isinstance(node, ast.FunctionDef) and node.name == "get_graph":
                line_number = node.lineno
                is_async = isinstance(node, ast.AsyncFunctionDef)

                return {
                    "line_number": line_number,
                    "type": "function_definition",
                    "function": "get_graph",
                    "is_async": is_async,
                    "arg_count": len(node.args.args),
                    "source_line": content.split("\n")[line_number - 1].strip(),
                }

            # Check for async get_graph function definition
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_graph":
                line_number = node.lineno

                return {
                    "line_number": line_number,
                    "type": "function_definition",
                    "function": "get_graph",
                    "is_async": True,
                    "arg_count": len(node.args.args),
                    "source_line": content.split("\n")[line_number - 1].strip(),
                }

            # Fallback: look for assignments to 'graph' variable
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
