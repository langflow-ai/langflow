"""Component code validation using static analysis only.

Security: This module validates LLM-generated component code WITHOUT executing it.
All checks use AST parsing and compilation — never exec() or eval().
The full runtime validation (imports, Pydantic, etc.) happens later when the
component is loaded into a flow via the standard create_class() path.
"""

import ast
import re

from lfx.custom.validate import extract_class_name
from pydantic import ValidationError

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

    # Langflow components commonly use async output methods
    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815


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


def _format_validation_error(exc: ValidationError) -> str:
    """Return a compact single-line message for a pydantic ValidationError.

    The retry loop in assistant_service feeds this string into
    extract_friendly_error, which pattern-matches on phrases like
    ``"input should be a valid"`` to route the error to a targeted corrective
    prompt. Pydantic's first error line is just ``"1 validation error for X"``
    — the actionable detail lives in subsequent lines — so we collapse the
    full error into one line to keep the downstream patterns matching.
    """
    errors = exc.errors()
    if errors:
        parts = []
        for err in errors[:3]:
            loc = ".".join(str(x) for x in err.get("loc", ()))
            msg = err.get("msg", "")
            parts.append(f"{loc}: {msg}" if loc else msg)
        return f"ValidationError: {'; '.join(parts)}"

    text = str(exc).replace("\n", " ").strip()
    return f"ValidationError: {text}" if text else "ValidationError"


def _format_root_error(exc: BaseException) -> str:
    """Collapse an exception chain to a compact, single-line error string."""
    root = exc.__cause__ or exc
    if isinstance(root, ValidationError):
        return _format_validation_error(root)

    error_type = type(root).__name__
    error_msg = str(root).split("\n")[0].strip() if str(root) else str(exc).split("\n")[0].strip()
    return f"{error_type}: {error_msg}" if error_msg else error_type


async def _execute_output_methods_for_validation(cc_instance) -> str | None:
    """Invoke every output method and surface pydantic-schema failures only.

    Executes ``cc_instance._build_results()`` — which calls every output method
    bound to the component — and catches ``pydantic.ValidationError`` (raised
    when a method constructs a schema object with the wrong shape, e.g.
    ``Data(data=[list])`` or ``Message(sender=<not-a-string>)``).

    Non-schema runtime errors (network failures, missing inputs, auth problems)
    are **intentionally swallowed**: a correct component can still fail
    execution in the validation sandbox for environmental reasons, and we must
    not mark it as broken on that basis. The retry loop in assistant_service
    consumes only the schema errors this helper returns.

    Note: uses ``_build_results`` directly instead of the public ``build_results``
    because the latter emits events via ``send_error`` and relies on a
    tracing/event manager that the validation sandbox does not wire up.
    """
    try:
        cc_instance.set_attributes({})
    except ValidationError as exc:
        return _format_root_error(exc)
    except (AttributeError, TypeError, ValueError):
        return None

    try:
        await cc_instance._build_results()  # noqa: SLF001 — sandbox bypass of send_error/tracing
    except ValidationError as exc:
        return _format_validation_error(exc)
    except Exception as exc:  # noqa: BLE001 — see sandbox rationale in docstring
        cause = exc.__cause__ or exc.__context__
        if isinstance(cause, ValidationError):
            return _format_validation_error(cause)
        return None
    return None


async def validate_component_runtime(code: str, user_id: str | None = None) -> str | None:
    """Try to instantiate and execute the component at runtime.

    Returns None if validation passes, or a compact error message string if
    it fails. Catches issues that static AST validation cannot detect:

    - Wrong import paths (e.g., ``from lfx.base import Component`` instead of
      ``from lfx.custom import Component``)
    - Missing dependencies
    - Invalid class hierarchy
    - **Pydantic-schema bugs raised while running the output methods**
      (e.g. ``Data(data=[list])`` when a dict is expected, ``Message`` built
      with the wrong field types, ``DataFrame`` with malformed rows, or any
      other pydantic model the component tries to construct)

    The execution step is a sandbox: non-schema runtime errors (network,
    filesystem, auth, missing inputs) are swallowed because a correctly
    generated component can legitimately fail in the sandbox for environmental
    reasons. Only pydantic-schema errors — which are almost always LLM-coding
    mistakes — are surfaced so the retry loop can recover before the component
    is handed to the user.
    """
    try:
        from lfx.custom.custom_component.component import Component as ComponentClass
        from lfx.custom.utils import build_custom_component_template

        component_instance = ComponentClass(_code=code)
        _, cc_instance = build_custom_component_template(component_instance, user_id=user_id)
    except Exception as e:  # noqa: BLE001 — compact one-line error for the retry prompt
        return _format_root_error(e)

    return await _execute_output_methods_for_validation(cc_instance)


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
