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


def _find_class_node(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Find the ClassDef node matching class_name in the AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _find_list_assign(class_node: ast.ClassDef, attr_name: str) -> ast.List | None:
    """Find a class-level `attr_name = [...]` assignment and return the List node."""
    for node in class_node.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == attr_name and isinstance(node.value, ast.List):
                return node.value
    return None


def _extract_str_kwarg(call_node: ast.Call, kwarg_name: str) -> str | None:
    """Extract a string keyword argument value from a Call node."""
    for kw in call_node.keywords:
        if kw.arg == kwarg_name and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _extract_io_names(tree: ast.Module, class_name: str) -> tuple[set[str], set[str]]:
    """Extract input and output names from component code using AST.

    Returns:
        Tuple of (input_names, output_names) as sets of strings.
    """
    class_node = _find_class_node(tree, class_name)
    if class_node is None:
        return set(), set()

    input_names: set[str] = set()
    inputs_list = _find_list_assign(class_node, "inputs")
    if inputs_list is not None:
        for elt in inputs_list.elts:
            if isinstance(elt, ast.Call):
                name = _extract_str_kwarg(elt, "name")
                if name is not None:
                    input_names.add(name)

    output_names: set[str] = set()
    outputs_list = _find_list_assign(class_node, "outputs")
    if outputs_list is not None:
        for elt in outputs_list.elts:
            if isinstance(elt, ast.Call):
                name = _extract_str_kwarg(elt, "name")
                if name is not None:
                    output_names.add(name)

    return input_names, output_names


def _extract_output_methods(tree: ast.Module, class_name: str) -> list[str]:
    """Extract output method names from Output(method="...") calls via AST."""
    class_node = _find_class_node(tree, class_name)
    if class_node is None:
        return []

    outputs_list = _find_list_assign(class_node, "outputs")
    if outputs_list is None:
        return []

    methods: list[str] = []
    for elt in outputs_list.elts:
        if isinstance(elt, ast.Call):
            method = _extract_str_kwarg(elt, "method")
            if method is not None:
                methods.append(method)
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

        tree = ast.parse(code)
        compile(ast.Module(body=tree.body, type_ignores=[]), "<string>", "exec")

        input_names, output_names = _extract_io_names(tree, class_name)
        overlap = input_names & output_names
        if overlap:
            msg = f"Inputs and outputs have overlapping names: {overlap}"
            raise ValueError(msg)

        output_methods = _extract_output_methods(tree, class_name)
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
