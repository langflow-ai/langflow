"""Security sandbox for custom component code validation.

Validates user-supplied Python code before execution during component
template building. Blocks dangerous module imports, restricts builtins,
and sanitizes AST nodes to prevent arbitrary code execution during the
validation phase.

Runtime execution (when flows are actually run) is NOT affected by these
checks — components can still use any module at runtime.

Configuration:
    Set LANGFLOW_SANDBOX_CUSTOM_CODE=false to disable sandbox checks
    (not recommended for production).
"""

import ast
import builtins
import os

# ---------------------------------------------------------------------------
# Blocked modules — never needed during *validation* (template building).
# Users who need these at runtime should keep them; the sandbox only applies
# to the validation path.
# ---------------------------------------------------------------------------
BLOCKED_MODULES: frozenset[str] = frozenset(
    {
        "subprocess",
        "socket",
        "pty",
        "shutil",
        "ctypes",
        "multiprocessing",
        "signal",
        "commands",
        "pdb",
        "code",
        "codeop",
        "http.server",
        "xmlrpc.server",
        "ftplib",
        "smtplib",
        "telnetlib",
        "poplib",
        "imaplib",
        "nntplib",
        "webbrowser",
        "antigravity",
        "turtle",
    }
)

# ---------------------------------------------------------------------------
# Builtins that are removed from the exec scope during sandboxed validation.
# ---------------------------------------------------------------------------
BLOCKED_BUILTINS: frozenset[str] = frozenset(
    {
        "__import__",
        "exec",
        "eval",
        "compile",
        "open",
        "breakpoint",
        "exit",
        "quit",
    }
)

SANDBOX_ENABLED: bool = os.getenv("LANGFLOW_SANDBOX_CUSTOM_CODE", "true").lower() in (
    "true",
    "1",
    "yes",
)


class CodeSafetyError(Exception):
    """Raised when user-supplied code fails safety validation."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_code_safety(code: str) -> None:
    """Run all safety checks on user-supplied component code.

    Raises CodeSafetyError if any check fails.
    Does nothing when the sandbox is disabled via environment variable.
    """
    if not SANDBOX_ENABLED:
        return

    _validate_imports(code)
    _validate_no_dangerous_builtins(code)


def create_restricted_builtins() -> dict:
    """Return a copy of Python builtins with dangerous names removed."""
    return {k: v for k, v in vars(builtins).items() if k not in BLOCKED_BUILTINS}


def filter_safe_definitions(definitions: list[ast.stmt]) -> list[ast.stmt]:
    """Filter a list of AST definition nodes, keeping only safe ones.

    Safe definitions:
    - ``ast.FunctionDef`` / ``ast.AsyncFunctionDef`` (method bodies are not
      executed during definition)
    - ``ast.Assign`` / ``ast.AnnAssign`` whose value does NOT contain any
      ``ast.Call`` node (i.e. no function/method invocations)

    ``ast.ClassDef`` nodes are **excluded** — they are handled separately via
    ``sanitize_class_body`` + ``build_class_constructor`` to ensure their
    bodies are sanitized before execution.

    This prevents top-level assignments like
    ``result = subprocess.check_output(...)`` from being executed, and
    prevents unsanitized class body code from running.
    """
    if not SANDBOX_ENABLED:
        return definitions

    safe: list[ast.stmt] = []
    for node in definitions:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            safe.append(node)
        elif isinstance(node, ast.Assign):
            if not _contains_call(node.value):
                safe.append(node)
        elif isinstance(node, ast.AnnAssign):
            if node.value is None or not _contains_call(node.value):
                safe.append(node)
        # ClassDef is intentionally excluded — handled via sanitize_class_body
        # Skip anything else (bare expressions, etc.)
    return safe


def sanitize_class_body(class_node: ast.ClassDef) -> ast.ClassDef:
    """Remove dangerous statements from a class body before exec.

    Keeps:
    - Method definitions (``FunctionDef``, ``AsyncFunctionDef``)
    - Safe assignments (no function calls in the value)
    - Nested class definitions
    - Docstrings (``Expr`` wrapping a ``Constant``)

    Removes:
    - Assignments whose value contains function calls
      (e.g. ``os.system("id")``)
    - Bare expression statements with function calls
    """
    if not SANDBOX_ENABLED:
        return class_node

    safe_body: list[ast.stmt] = []
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            safe_body.append(node)
        elif isinstance(node, ast.Assign):
            if not _contains_call(node.value):
                safe_body.append(node)
            # else: skip — e.g. ``os.system("id")`` assigned to a variable
        elif isinstance(node, ast.AnnAssign):
            if node.value is None or not _contains_call(node.value):
                safe_body.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            safe_body.append(node)  # docstring
        # Skip bare function calls, attribute calls, etc.

    # A class body must have at least one statement
    if not safe_body:
        safe_body = [ast.Pass()]

    class_node.body = safe_body
    ast.fix_missing_locations(class_node)
    return class_node


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_imports(code: str) -> None:
    """Check that the code does not import any blocked module."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return  # syntax errors are caught later by the compiler

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module_blocked(alias.name, node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _check_module_blocked(node.module, node.lineno)


def _validate_no_dangerous_builtins(code: str) -> None:
    """Detect calls to dangerous builtins like __import__, exec, eval."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    dangerous_names = {"__import__", "exec", "eval", "compile"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in dangerous_names:
                raise CodeSafetyError(
                    f"Call to '{node.func.id}()' is not allowed in custom component code "
                    f"(line {node.lineno}). This function can execute arbitrary code."
                )


def _check_module_blocked(module_name: str, lineno: int) -> None:
    """Raise CodeSafetyError if *module_name* matches any blocked module."""
    # Check the module name and all its parent packages
    parts = module_name.split(".")
    for i in range(len(parts)):
        prefix = ".".join(parts[: i + 1])
        if prefix in BLOCKED_MODULES:
            raise CodeSafetyError(
                f"Import of '{module_name}' is blocked during component validation "
                f"(line {lineno}). If this import is needed at runtime, keep it in "
                f"your component — it will work when the flow is executed."
            )


def _contains_call(node: ast.AST) -> bool:
    """Return True if *node* or any descendant is an ``ast.Call``."""
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            return True
    return False
