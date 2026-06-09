"""Security scanning for LLM-generated component code.

Security: Analyzes generated Python code for dangerous patterns using AST.
Never executes the code. Called AFTER code extraction, BEFORE returning to user.
"""

import ast
from dataclasses import dataclass, field

# Dangerous function calls that should never appear in component code
DANGEROUS_CALLS: dict[str, str] = {
    "exec": "Use of exec() is forbidden in components",
    "eval": "Use of eval() is forbidden in components",
    "compile": "Use of compile() is forbidden in components",
    "__import__": "Use of __import__() is forbidden in components",
    "globals": "Use of globals() is forbidden in components",
}

# Dangerous attribute calls: (module, method, violation_message)
DANGEROUS_ATTR_CALLS: list[tuple[str, str, str]] = [
    ("os", "system", "os.system() is forbidden — use Langflow's built-in integrations"),
    ("os", "popen", "os.popen() is forbidden"),
    ("os", "execl", "os.execl() is forbidden"),
    ("os", "execle", "os.execle() is forbidden"),
    ("os", "execlp", "os.execlp() is forbidden"),
    ("os", "execv", "os.execv() is forbidden"),
    ("os", "execve", "os.execve() is forbidden"),
    ("os", "execvp", "os.execvp() is forbidden"),
    ("os", "execvpe", "os.execvpe() is forbidden"),
    ("os", "spawn", "os.spawn*() is forbidden"),
    ("os", "spawnl", "os.spawnl() is forbidden"),
    ("os", "remove", "os.remove() is forbidden in components"),
    ("os", "rmdir", "os.rmdir() is forbidden in components"),
    ("os", "unlink", "os.unlink() is forbidden in components"),
    ("subprocess", "run", "subprocess.run() is forbidden"),
    ("subprocess", "call", "subprocess.call() is forbidden"),
    ("subprocess", "Popen", "subprocess.Popen() is forbidden"),
    ("subprocess", "check_output", "subprocess.check_output() is forbidden"),
    ("subprocess", "check_call", "subprocess.check_call() is forbidden"),
    ("shutil", "rmtree", "shutil.rmtree() is forbidden"),
    ("shutil", "move", "shutil.move() is forbidden in components"),
    ("sys", "exit", "sys.exit() is forbidden in components"),
]

# Imports that are forbidden entirely
DANGEROUS_IMPORTS: set[str] = {
    "subprocess",
    "shutil",
    "ctypes",
    "pickle",
    "shelve",
    "marshal",
    "code",
    "codeop",
    "compileall",
    "importlib",
}

# Imports where only specific names are dangerous (module -> set of dangerous names)
RESTRICTED_IMPORT_NAMES: dict[str, set[str]] = {
    "os": {
        "system",
        "popen",
        "execl",
        "execle",
        "execlp",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "remove",
        "rmdir",
        "unlink",
    },
}


@dataclass(frozen=True)
class SecurityScanResult:
    """Result of code security scan."""

    is_safe: bool
    violations: tuple[str, ...] = field(default_factory=tuple)


class _SecurityChecker(ast.NodeVisitor):
    """AST visitor that detects dangerous patterns in generated code."""

    def __init__(self):
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module in DANGEROUS_IMPORTS:
                self.violations.append(f"Import of '{alias.name}' is forbidden in components")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if not node.module:
            return self.generic_visit(node)

        root_module = node.module.split(".")[0]

        if root_module in DANGEROUS_IMPORTS:
            self.violations.append(f"Import from '{node.module}' is forbidden in components")
        elif root_module in RESTRICTED_IMPORT_NAMES and node.names:
            restricted = RESTRICTED_IMPORT_NAMES[root_module]
            for alias in node.names:
                if alias.name in restricted:
                    self.violations.append(f"Import of '{root_module}.{alias.name}' is forbidden in components")

        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        self._check_name_call(node)
        self._check_attribute_call(node)
        self.generic_visit(node)

    def _check_name_call(self, node: ast.Call):
        """Check direct function calls like exec(), eval()."""
        if isinstance(node.func, ast.Name) and node.func.id in DANGEROUS_CALLS:
            self.violations.append(DANGEROUS_CALLS[node.func.id])

    def _check_attribute_call(self, node: ast.Call):
        """Check attribute calls like os.system(), subprocess.run()."""
        if not isinstance(node.func, ast.Attribute):
            return
        if not isinstance(node.func.value, ast.Name):
            return

        module_name = node.func.value.id
        method_name = node.func.attr

        for mod, method, message in DANGEROUS_ATTR_CALLS:
            if module_name == mod and method_name == method:
                self.violations.append(message)
                return


def scan_code_security(code: str) -> SecurityScanResult:
    """Scan generated code for security violations using AST analysis.

    Security: This function MUST NOT execute the code.
    All checks use AST parsing only.

    Returns SecurityScanResult with is_safe=True if no violations found.
    SyntaxError in code returns is_safe=True (syntax is validated by validation.py).
    """
    if not code or not code.strip():
        return SecurityScanResult(is_safe=True)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return SecurityScanResult(is_safe=True)

    checker = _SecurityChecker()
    checker.visit(tree)

    return SecurityScanResult(
        is_safe=len(checker.violations) == 0,
        violations=tuple(checker.violations),
    )
