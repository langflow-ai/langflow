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
    """Create a FunctionComponent class from pure function code.

    Function selection rules:
    - If there's exactly one function, use it (implicit component)
    - If there are multiple functions, look for one with @component decorator
    - If multiple functions exist and none/multiple are decorated, raise an error
    """
    from lfx.base.functions import FunctionComponent

    # Dedent the code to handle indented function definitions
    dedented_code = textwrap.dedent(code)

    # Execute code to get the functions
    namespace: dict = {}
    exec(dedented_code, namespace)  # noqa: S102

    # Parse and analyze all functions
    tree = ast.parse(dedented_code)
    functions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    decorated_functions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append((node.name, node))
            # Check if this function has @component decorator
            if _has_component_decorator(node):
                decorated_functions.append((node.name, node))

    if not functions:
        msg = "No function found in code"
        raise ValueError(msg)

    # Determine which function to use
    if len(functions) == 1:
        # Single function: use it implicitly
        func_name = functions[0][0]
    elif len(decorated_functions) == 1:
        # Multiple functions but exactly one decorated: use the decorated one
        func_name = decorated_functions[0][0]
    elif len(decorated_functions) == 0:
        # Multiple functions, none decorated: ambiguous
        func_names = [f[0] for f in functions]
        msg = (
            f"Multiple functions found ({', '.join(func_names)}) but none has @component decorator. "
            f"Either use a single function or add @component decorator to specify which function to use."
        )
        raise ValueError(msg)
    else:
        # Multiple functions, multiple decorated: ambiguous
        decorated_names = [f[0] for f in decorated_functions]
        msg = (
            f"Multiple functions with @component decorator found ({', '.join(decorated_names)}). "
            f"Only one function can be decorated with @component."
        )
        raise ValueError(msg)

    func = namespace.get(func_name)
    if func is None:
        msg = f"Function '{func_name}' not found in namespace after execution"
        raise ValueError(msg)

    # Create a factory class that behaves like a Component class
    # but returns FunctionComponent instances
    class FunctionComponentWrapper(FunctionComponent):
        def __init__(self, **kwargs):
            super().__init__(func=func, _source_code=dedented_code, **kwargs)

    FunctionComponentWrapper.__name__ = f"FunctionComponent_{func_name}"
    return FunctionComponentWrapper


def _has_component_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function has the @component decorator."""
    for decorator in node.decorator_list:
        # Handle @component
        if isinstance(decorator, ast.Name) and decorator.id == "component":
            return True
        # Handle @component(...) with arguments
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name) and decorator.func.id == "component":
                return True
            # Handle lfx.base.functions.component
            if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "component":
                return True
        # Handle lfx.base.functions.component (without call)
        if isinstance(decorator, ast.Attribute) and decorator.attr == "component":
            return True
    return False
