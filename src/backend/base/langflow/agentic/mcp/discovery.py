"""Automatic function discovery for MCP tools.

This module automatically discovers and wraps functions from the agentic
folder to be exposed as MCP tools.
"""

import importlib
import inspect
from pathlib import Path
from typing import Any, Callable

from .config import TOOL_CONFIGS, get_tool_config, is_tool_enabled


def get_function_signature(func: Callable) -> dict[str, Any]:
    """Extract JSON schema from function signature.

    Args:
        func: The function to analyze

    Returns:
        JSON schema describing the function parameters
    """
    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        param_schema: dict[str, Any] = {}

        # Get type annotation
        if param.annotation != inspect.Parameter.empty:
            annotation = param.annotation

            # Handle Union types (e.g., str | None)
            if hasattr(annotation, "__origin__"):
                if annotation.__origin__ is type(None) or str(annotation).startswith("typing.Union"):
                    # It's an optional type
                    # Extract the non-None type
                    args = getattr(annotation, "__args__", ())
                    non_none_types = [arg for arg in args if arg is not type(None)]
                    if non_none_types:
                        param_schema["type"] = _python_type_to_json_type(non_none_types[0])
                else:
                    param_schema["type"] = _python_type_to_json_type(annotation)
            else:
                param_schema["type"] = _python_type_to_json_type(annotation)

        # Check if parameter has default value
        if param.default == inspect.Parameter.empty:
            required.append(param_name)
        else:
            param_schema["default"] = param.default

        # Extract description from docstring if available
        doc = inspect.getdoc(func)
        if doc:
            param_desc = _extract_param_description(doc, param_name)
            if param_desc:
                param_schema["description"] = param_desc

        properties[param_name] = param_schema

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _python_type_to_json_type(python_type: Any) -> str:
    """Convert Python type to JSON schema type.

    Args:
        python_type: Python type annotation

    Returns:
        JSON schema type string
    """
    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    # Handle string representations
    if isinstance(python_type, str):
        type_lower = python_type.lower()
        if "str" in type_lower:
            return "string"
        if "int" in type_lower:
            return "integer"
        if "float" in type_lower or "number" in type_lower:
            return "number"
        if "bool" in type_lower:
            return "boolean"
        if "list" in type_lower:
            return "array"
        if "dict" in type_lower:
            return "object"

    # Try direct mapping
    return type_mapping.get(python_type, "string")


def _extract_param_description(docstring: str, param_name: str) -> str | None:
    """Extract parameter description from docstring.

    Args:
        docstring: The function's docstring
        param_name: The parameter name to find

    Returns:
        Parameter description if found, None otherwise
    """
    lines = docstring.split("\n")
    in_args_section = False

    for line in lines:
        stripped = line.strip()

        # Check if we're entering Args section
        if stripped.lower().startswith("args:"):
            in_args_section = True
            continue

        # Check if we're leaving Args section
        if in_args_section and stripped and stripped[0].isupper() and stripped.endswith(":"):
            in_args_section = False
            continue

        # Look for parameter in Args section
        if in_args_section and stripped.startswith(f"{param_name}"):
            # Extract description after the colon
            parts = stripped.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()

    return None


def discover_functions(module_path: str) -> dict[str, Callable]:
    """Discover all enabled functions from a module.

    Args:
        module_path: The module path relative to langflow.agentic (e.g., "utils.template_search")

    Returns:
        Dictionary mapping function names to function objects
    """
    full_module_path = f"langflow.agentic.{module_path}"

    try:
        module = importlib.import_module(full_module_path)
    except ImportError as e:
        print(f"Warning: Could not import {full_module_path}: {e}")
        return {}

    functions = {}

    # Get all functions from the module
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        # Skip private functions
        if name.startswith("_"):
            continue

        # Check if function is enabled in config
        if is_tool_enabled(module_path, name):
            functions[name] = obj

    return functions


def discover_all_tools() -> dict[str, dict[str, Any]]:
    """Discover all enabled tools from configured modules.

    Returns:
        Dictionary mapping tool names to their metadata:
        {
            "list_templates": {
                "function": <function>,
                "config": <ToolConfig>,
                "schema": <dict>
            },
            ...
        }
    """
    all_tools = {}

    for module_path, function_configs in TOOL_CONFIGS.items():
        # Discover functions from this module
        functions = discover_functions(module_path)

        for func_name, func in functions.items():
            # Get tool configuration
            config = get_tool_config(module_path, func_name)
            if not config or not config.enabled:
                continue

            # Use custom name if provided, otherwise use function name
            tool_name = config.name or func_name

            # Get function schema
            schema = get_function_signature(func)

            # Override with custom schema if provided
            if config.parameters_schema:
                schema = config.parameters_schema

            # Get description
            description = config.description or inspect.getdoc(func) or f"Tool: {tool_name}"

            all_tools[tool_name] = {
                "function": func,
                "config": config,
                "schema": schema,
                "description": description,
                "module_path": module_path,
                "function_name": func_name,
            }

    return all_tools


def get_tool_list() -> list[dict[str, Any]]:
    """Get a list of all available tools with their metadata.

    Returns:
        List of tool metadata dictionaries
    """
    tools = discover_all_tools()

    return [
        {
            "name": name,
            "description": metadata["description"],
            "input_schema": metadata["schema"],
        }
        for name, metadata in tools.items()
    ]
