import ast
import textwrap
from typing import TYPE_CHECKING

from lfx.custom import validate

if TYPE_CHECKING:
    from lfx.custom.custom_component.custom_component import CustomComponent


def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Evaluate custom component code.

    Handles both class-based components and function-based components.
    """
    # Check if this is pure function code (no Component class)
    if _is_function_code(code):
        return _create_function_component_class(code)

    # Existing class-based logic
    class_name = validate.extract_class_name(code)
    return validate.create_class(code, class_name)


def _is_function_code(code: str) -> bool:
    """Check if code is a function definition (not a Component class).

    This handles two cases:
    1. Plain function code (from serialization, decorator already stripped)
    2. Code with @component decorator (from UI input)
    """
    try:
        # Dedent the code to handle indented function definitions
        dedented_code = textwrap.dedent(code)
        tree = ast.parse(dedented_code)
    except SyntaxError:
        return False

    has_function = False
    has_component_class = False

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            has_function = True
        elif isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and any(pattern in base.id for pattern in ["Component", "LC"]):
                    has_component_class = True

    # If there's a Component class, it's class-based code
    if has_component_class:
        return False

    # Must have at least one function to be function code
    return has_function


def _create_function_component_class(code: str) -> type:
    """Create a FunctionComponent class from pure function code."""
    from lfx.base.functions import FunctionComponent

    # Dedent the code to handle indented function definitions
    dedented_code = textwrap.dedent(code)

    # Execute code to get the function
    namespace: dict = {}
    exec(dedented_code, namespace)  # noqa: S102

    # Find the first function defined in the code
    func = None
    func_name = None
    tree = ast.parse(dedented_code)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            func = namespace.get(func_name)
            break

    if func is None:
        msg = "No function found in code"
        raise ValueError(msg)

    # Create a factory class that behaves like a Component class
    # but returns FunctionComponent instances
    class FunctionComponentWrapper(FunctionComponent):
        def __init__(self, **kwargs):
            super().__init__(func=func, _source_code=dedented_code, **kwargs)

    FunctionComponentWrapper.__name__ = f"FunctionComponent_{func_name}"
    return FunctionComponentWrapper
