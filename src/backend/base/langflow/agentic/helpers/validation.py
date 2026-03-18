"""Component code validation using static analysis only.

Security: This module validates LLM-generated component code WITHOUT executing it.
All checks use AST parsing and compilation — never exec() or eval().
The full runtime validation (imports, Pydantic, etc.) happens later when the
component is loaded into a flow via the standard create_class() path.
"""

import ast
import re

from lfx.custom.validate import extract_class_name

from langflow.agentic.api.schemas import ValidationResult

# Regex pattern to extract class name that inherits from Component
CLASS_NAME_PATTERN = re.compile(r"class\s+(\w+)\s*\([^)]*Component[^)]*\)")


class _ReturnChecker(ast.NodeVisitor):
    """Check which methods have return statements with values."""

    def __init__(self):
        self.methods_with_return: set[str] = set()

    def visit_FunctionDef(self, node):
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value is not None:
                self.methods_with_return.add(node.name)
                break
        self.generic_visit(node)


def _extract_class_name_regex(code: str) -> str | None:
    """Extract class name using regex (fallback for syntax errors)."""
    match = CLASS_NAME_PATTERN.search(code)
    return match.group(1) if match else None


def _safe_extract_class_name(code: str) -> str | None:
    """Extract class name with fallback to regex for broken code."""
    try:
        return extract_class_name(code)
    except (ValueError, SyntaxError, TypeError):
        return _extract_class_name_regex(code)


def _extract_io_names_from_ast(code: str, class_name: str) -> tuple[set[str], set[str]]:
    """Extract input and output names from component code using AST only.

    Parses the class body looking for `inputs = [...]` and `outputs = [...]`
    assignments, then extracts `name` keyword arguments from the Call nodes.

    Returns:
        Tuple of (input_names, output_names) as sets of strings.
    """
    input_names: set[str] = set()
    output_names: set[str] = set()

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return input_names, output_names

    # Find the target class
    class_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_node = node
            break

    if class_node is None:
        return input_names, output_names

    for node in class_node.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "inputs" and isinstance(node.value, ast.List):
                input_names = _extract_names_from_call_list(node.value)
            elif target.id == "outputs" and isinstance(node.value, ast.List):
                output_names = _extract_names_from_call_list(node.value)

    return input_names, output_names


def _extract_names_from_call_list(list_node: ast.List) -> set[str]:
    """Extract 'name' keyword argument values from a list of Call nodes."""
    names: set[str] = set()
    for elt in list_node.elts:
        if not isinstance(elt, ast.Call):
            continue
        for kw in elt.keywords:
            if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                names.add(kw.value.value)
    return names


def _extract_output_methods_from_ast(code: str, class_name: str) -> list[str]:
    """Extract output method names from the outputs list via AST.

    Returns list of method name strings from Output(method="...") calls.
    """
    methods: list[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return methods

    class_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_node = node
            break

    if class_node is None:
        return methods

    for node in class_node.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "outputs" and isinstance(node.value, ast.List):
                for elt in node.value.elts:
                    if not isinstance(elt, ast.Call):
                        continue
                    for kw in elt.keywords:
                        if (
                            kw.arg == "method"
                            and isinstance(kw.value, ast.Constant)
                            and isinstance(kw.value.value, str)
                        ):
                            methods.append(kw.value.value)

    return methods


def validate_component_code(code: str) -> ValidationResult:
    """Validate component code using static analysis only.

    Security: This function MUST NOT execute the code via exec() or eval().
    All validation is performed via AST parsing and compile() checks.
    The full runtime validation happens when the component is loaded into a flow.

    Checks performed:
    1. Syntax validity (ast.parse + compile)
    2. Class name extraction
    3. Overlapping input/output names
    4. Output methods have return statements with values
    """
    class_name = _safe_extract_class_name(code)

    try:
        if class_name is None:
            msg = "Could not extract class name from code"
            raise ValueError(msg)

        # Static check: parse and compile without executing
        tree = ast.parse(code)
        compile(ast.Module(body=tree.body, type_ignores=[]), "<string>", "exec")

        # Check for overlapping input/output names (AST-only)
        input_names, output_names = _extract_io_names_from_ast(code, class_name)
        overlap = input_names & output_names
        if overlap:
            msg = f"Inputs and outputs have overlapping names: {overlap}"
            raise ValueError(msg)

        # Check that output methods have return statements with values
        output_methods = _extract_output_methods_from_ast(code, class_name)
        if output_methods:
            checker = _ReturnChecker()
            checker.visit(tree)
            for method_name in output_methods:
                if method_name not in checker.methods_with_return:
                    return ValidationResult(
                        is_valid=False,
                        code=code,
                        error=f"Output method '{method_name}' does not have a return statement with a value",
                        class_name=class_name,
                    )

        return ValidationResult(is_valid=True, code=code, class_name=class_name)
    except (ValueError, TypeError, SyntaxError) as e:
        return ValidationResult(
            is_valid=False,
            code=code,
            error=f"{type(e).__name__}: {e}",
            class_name=class_name,
        )
