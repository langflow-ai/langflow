"""Validation utilities for lfx custom components."""

import ast
from typing import Any


def extract_function_name(code: str) -> str:
    """Extract the name of the first function found in the code.

    Args:
        code: The source code to parse

    Returns:
        str: Name of the first function found

    Raises:
        ValueError: If no function definition is found in the code
    """
    try:
        module = ast.parse(code)
        for node in module.body:
            if isinstance(node, ast.FunctionDef):
                return node.name
        msg = "No function definition found in the code string"
        raise ValueError(msg)
    except SyntaxError as e:
        msg = f"Invalid Python code: {e!s}"
        raise ValueError(msg) from e


def extract_class_name(code: str) -> str:
    """Extract the name of the first Component subclass found in the code.

    Args:
        code: The source code to parse

    Returns:
        str: Name of the first Component subclass found

    Raises:
        TypeError: If no Component subclass is found in the code
        ValueError: If the code contains syntax errors
    """
    try:
        module = ast.parse(code)
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue

            # Check bases for Component inheritance
            # TODO: Build a more robust check for Component inheritance
            for base in node.bases:
                if isinstance(base, ast.Name) and any(pattern in base.id for pattern in ["Component", "LC"]):
                    return node.name

        msg = f"No Component subclass found in the code string. Code snippet: {code[:100]}"
        raise TypeError(msg)
    except SyntaxError as e:
        msg = f"Invalid Python code: {e!s}"
        raise ValueError(msg) from e


def create_class(code: str, class_name: str) -> Any:
    """Dynamically create a class from a string of code and a specified class name.

    This is a simplified version that focuses on creating classes for lfx custom components.
    For the full implementation with all dependencies, use langflow.utils.validate.create_class.

    Args:
        code: String containing the Python code defining the class
        class_name: Name of the class to be created

    Returns:
        A function that, when called, returns an instance of the created class

    Raises:
        ValueError: If the code contains syntax errors or the class definition is invalid
    """
    # Import the full implementation from langflow utils
    from langflow.utils.validate import create_class as langflow_create_class

    return langflow_create_class(code, class_name)


def create_function(code: str, function_name: str) -> Any:
    """Create a function from code string.

    This is a simplified version for lfx. For the full implementation,
    use langflow.utils.validate.create_function.

    Args:
        code: String containing the Python code defining the function
        function_name: Name of the function to be created

    Returns:
        The created function

    Raises:
        ValueError: If the code contains syntax errors or the function definition is invalid
    """
    # Import the full implementation from langflow utils
    from langflow.utils.validate import create_function as langflow_create_function

    return langflow_create_function(code, function_name)
