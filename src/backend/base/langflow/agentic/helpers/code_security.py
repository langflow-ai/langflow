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
    # Raw file access — components must use Langflow's File components,
    # not open arbitrary paths (e.g. /etc/passwd, SSH keys).
    "open": "Use of open() is forbidden in components — use Langflow's File components",
    "breakpoint": "Use of breakpoint() is forbidden in components",
}

# Attribute names that are sandbox-escape vectors regardless of the
# object they're read from (e.g. ``().__class__.__bases__[0]
# .__subclasses__()``, ``func.__globals__``). Near-zero legitimate use
# in a component; deliberately tight to avoid false positives (NOT
# flagging benign dunders like ``__class__`` / ``__dict__`` / ``__name__``).
DANGEROUS_DUNDER_ATTRS: set[str] = {
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__bases__",
    "__mro__",
    "__code__",
    "__closure__",
    "__subclasshook__",
}

# Non-call attribute *reads* that are forbidden: (module, attr, message).
# Secret/env exfiltration is the concrete threat — components must use
# Langflow's variable/secret service, never raw process env.
DANGEROUS_ATTRIBUTE_READS: list[tuple[str, str, str]] = [
    ("os", "environ", "os.environ is forbidden — use Langflow's variable/secret service"),
    ("sys", "modules", "sys.modules is forbidden in components"),
]

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
    # File-descriptor redirection wires a socket to a shell (reverse shell).
    ("os", "dup2", "os.dup2() is forbidden in components"),
    ("os", "dup", "os.dup() is forbidden in components"),
    ("os", "getenv", "os.getenv() is forbidden — use Langflow's variable/secret service"),
    ("os", "putenv", "os.putenv() is forbidden in components"),
    ("shutil", "rmtree", "shutil.rmtree() is forbidden"),
    ("shutil", "move", "shutil.move() is forbidden in components"),
    ("sys", "exit", "sys.exit() is forbidden in components"),
]

# Imports that are forbidden entirely
DANGEROUS_IMPORTS: set[str] = {
    "subprocess",
    "shutil",
    # Native FFI modules can load arbitrary shared libraries. Include the
    # lower-level backends so blocking only the public frontends is not bypassable.
    "ctypes",
    "_ctypes",
    "cffi",
    "_cffi_backend",
    "pickle",
    "shelve",
    "marshal",
    "code",
    "codeop",
    "compileall",
    "importlib",
    # Network / IPC primitives — same attack class as subprocess (reverse
    # shells, raw exfil, SSRF, non-HTTP protocol egress). High-level HTTP via
    # ``requests``/``httpx`` stays allowed by design (legit API components need
    # it); these provide raw sockets and non-HTTP channels a component never
    # legitimately needs.
    "socket",
    "socketserver",
    "ftplib",
    "telnetlib",
    "smtplib",
    "poplib",
    "imaplib",
    "nntplib",
    "xmlrpc",
    # Pseudo-terminal — spawns an interactive shell (pty.spawn).
    "pty",
}

# Dangerous *submodules* of packages that also expose safe siblings. Block the
# dotted prefix while leaving the safe parts of the package importable (e.g.
# ``urllib.parse`` for urlencode/quote, ``from http import HTTPStatus``).
# ``urllib.request`` additionally supports ``file://`` / ``ftp://`` schemes, so
# it is a local-file-read and SSRF bypass beyond what plain HTTP allows.
DANGEROUS_SUBMODULES: tuple[str, ...] = (
    "urllib.request",
    "urllib.error",
    "http.client",
    "http.server",
)

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
        "dup2",
        "dup",
    },
    "sys": {"modules"},
}


def _is_dangerous_submodule(dotted: str) -> bool:
    """True if a dotted module path is (or is under) a blocked submodule.

    e.g. ``urllib.request`` and ``urllib.request.foo`` match; ``urllib`` and
    ``urllib.parse`` do not.
    """
    return any(dotted == prefix or dotted.startswith(prefix + ".") for prefix in DANGEROUS_SUBMODULES)


def _dotted_parts(node: ast.AST) -> list[str] | None:
    """Reconstruct a pure ``a.b.c`` Name/Attribute chain into ``["a", "b", "c"]``.

    Returns None if the chain is not rooted in a plain Name (e.g. ``foo().bar``).
    """
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return list(reversed(parts))
    return None


def _build_dangerous_members() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Per-module dangerous member names, derived from the call/read tables.

    Used to catch wildcard imports (``from os import *``) where a restricted
    member is then referenced as a bare name (``dup2(...)`` / ``environ[...]``).
    Kept in sync automatically so a new entry in the tables above is covered.
    """
    call_members: dict[str, set[str]] = {}
    for mod, method, _ in DANGEROUS_ATTR_CALLS:
        call_members.setdefault(mod, set()).add(method)
    for mod, names in RESTRICTED_IMPORT_NAMES.items():
        call_members.setdefault(mod, set()).update(names)

    read_members: dict[str, set[str]] = {}
    for mod, attr, _ in DANGEROUS_ATTRIBUTE_READS:
        read_members.setdefault(mod, set()).add(attr)

    return call_members, read_members


_DANGEROUS_CALL_MEMBERS, _DANGEROUS_READ_MEMBERS = _build_dangerous_members()

_AliasState = tuple[dict[str, frozenset[str]], set[str]]


def _collect_imports(tree: ast.AST) -> tuple[dict[str, str], set[str]]:
    """Map local binding names to canonical modules; collect ``import *`` modules.

    Resolves alias bypasses (``import os as o`` → ``o`` maps to ``os``) and
    wildcard bypasses (``from os import *``) so the checks below see them as
    plain ``os.<member>`` access. Order-independent (whole-tree walk).
    """
    aliases: dict[str, str] = {}
    wildcard_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    aliases[top] = top
        elif isinstance(node, ast.ImportFrom) and node.module and any(a.name == "*" for a in node.names):
            wildcard_modules.add(node.module.split(".")[0])
    return aliases, wildcard_modules


@dataclass(frozen=True)
class SecurityScanResult:
    """Result of code security scan."""

    is_safe: bool
    violations: tuple[str, ...] = field(default_factory=tuple)


class _SecurityChecker(ast.NodeVisitor):
    """AST visitor that detects dangerous patterns in generated code."""

    def __init__(self, module_aliases: dict[str, str] | None = None, wildcard_modules: set[str] | None = None):
        self.violations: list[str] = []
        # local-name -> possible canonical module values. A set is needed when
        # control-flow branches bind the same name differently.
        self.module_aliases: dict[str, frozenset[str]] = {
            name: frozenset({module}) for name, module in (module_aliases or {}).items()
        }
        # Names explicitly rebound to non-module values must not fall back to
        # their spelling (e.g. ``os = object(); os.system()`` is not os.system).
        self.shadowed_aliases: set[str] = set()
        # modules pulled in via ``from <mod> import *``.
        self.wildcard_modules: set[str] = wildcard_modules or set()

    def _resolved_names(self, name: str) -> frozenset[str]:
        """Return possible canonical values for a local name."""
        if name in self.shadowed_aliases:
            return frozenset()
        return self.module_aliases.get(name, frozenset({name}))

    def _resolved_assignment_value(self, node: ast.AST) -> frozenset[str]:
        """Resolve a simple Name/Attribute RHS without executing it."""
        if isinstance(node, ast.Name):
            return self._resolved_names(node.id)
        parts = _dotted_parts(node)
        if not parts:
            return frozenset()
        return frozenset(".".join([root, *parts[1:]]) for root in self._resolved_names(parts[0]))

    def _bind_name(self, name: str, values: frozenset[str]) -> None:
        if values:
            self.module_aliases[name] = values
            self.shadowed_aliases.discard(name)
        else:
            self.module_aliases.pop(name, None)
            self.shadowed_aliases.add(name)

    def _bind_assignment_target(self, target: ast.AST, value: ast.AST) -> None:
        """Apply assignment aliasing, including matching tuple/list unpacking."""
        if isinstance(target, ast.Name):
            self._bind_name(target.id, self._resolved_assignment_value(value))
        elif isinstance(target, ast.Starred):
            self._bind_assignment_target(target.value, value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            if isinstance(value, (ast.Tuple, ast.List)):
                starred_index = next(
                    (
                        index
                        for index, target_element in enumerate(target.elts)
                        if isinstance(target_element, ast.Starred)
                    ),
                    None,
                )
                if starred_index is None and len(target.elts) == len(value.elts):
                    for target_element, value_element in zip(target.elts, value.elts, strict=True):
                        self._bind_assignment_target(target_element, value_element)
                    return
                if starred_index is not None and len(value.elts) >= len(target.elts) - 1:
                    for target_element, value_element in zip(
                        target.elts[:starred_index], value.elts[:starred_index], strict=True
                    ):
                        self._bind_assignment_target(target_element, value_element)

                    trailing_count = len(target.elts) - starred_index - 1
                    if trailing_count:
                        for target_element, value_element in zip(
                            target.elts[-trailing_count:], value.elts[-trailing_count:], strict=True
                        ):
                            self._bind_assignment_target(target_element, value_element)

                    remaining_end = len(value.elts) - trailing_count if trailing_count else len(value.elts)
                    remaining_values = ast.List(
                        elts=value.elts[starred_index:remaining_end],
                        ctx=ast.Load(),
                    )
                    self._bind_assignment_target(target.elts[starred_index], remaining_values)
                    return

            for target_element in target.elts:
                self._bind_assignment_target(target_element, value)

    def _bind_iterated_target(self, target: ast.AST, iterable: ast.AST) -> None:
        """Bind a loop target to every statically visible iterable value."""
        if isinstance(iterable, (ast.List, ast.Tuple, ast.Set)):
            values = iterable.elts
        elif isinstance(iterable, ast.Dict):
            values = [key for key in iterable.keys if key is not None]
        else:
            values = [iterable]

        before_iteration = self._snapshot_alias_state()
        iteration_states: list[_AliasState] = []
        for value in values:
            self._restore_alias_state(before_iteration)
            self._bind_assignment_target(target, value)
            iteration_states.append(self._snapshot_alias_state())

        if iteration_states:
            self._merge_alias_states(iteration_states)
        else:
            self._bind_assignment_target(target, iterable)

    def _snapshot_alias_state(self) -> _AliasState:
        return self.module_aliases.copy(), self.shadowed_aliases.copy()

    def _restore_alias_state(self, state: _AliasState) -> None:
        aliases, shadowed = state
        self.module_aliases = aliases.copy()
        self.shadowed_aliases = shadowed.copy()

    def _restore_target_names(self, target_names: set[str], state: _AliasState) -> None:
        aliases, shadowed = state
        for name in target_names:
            if name in aliases:
                self.module_aliases[name] = aliases[name]
                self.shadowed_aliases.discard(name)
            elif name in shadowed:
                self.module_aliases.pop(name, None)
                self.shadowed_aliases.add(name)
            else:
                self.module_aliases.pop(name, None)
                self.shadowed_aliases.discard(name)

    def _assignment_target_names(self, target: ast.AST) -> set[str]:
        if isinstance(target, ast.Name):
            return {target.id}
        if isinstance(target, ast.Starred):
            return self._assignment_target_names(target.value)
        if isinstance(target, (ast.Tuple, ast.List)):
            return set().union(*(self._assignment_target_names(element) for element in target.elts))
        return set()

    def _merge_alias_states(self, states: list[_AliasState]) -> None:
        """Conservatively retain every module value reachable from a branch."""
        names = set().union(*(set(aliases) | shadowed for aliases, shadowed in states))
        merged_aliases: dict[str, frozenset[str]] = {}
        merged_shadowed: set[str] = set()
        for name in names:
            possible_values: set[str] = set()
            for aliases, shadowed in states:
                if name in aliases:
                    possible_values.update(aliases[name])
                elif name not in shadowed:
                    possible_values.add(name)
            if possible_values:
                merged_aliases[name] = frozenset(possible_values)
            else:
                merged_shadowed.add(name)
        self.module_aliases = merged_aliases
        self.shadowed_aliases = merged_shadowed

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module in DANGEROUS_IMPORTS or _is_dangerous_submodule(alias.name):
                self.violations.append(f"Import of '{alias.name}' is forbidden in components")
            binding = alias.asname or module
            imported_name = alias.name if alias.asname else module
            self._bind_name(binding, frozenset({imported_name}))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if not node.module:
            return self.generic_visit(node)

        root_module = node.module.split(".")[0]

        if root_module in DANGEROUS_IMPORTS or _is_dangerous_submodule(node.module):
            self.violations.append(f"Import from '{node.module}' is forbidden in components")
        elif root_module in RESTRICTED_IMPORT_NAMES and node.names:
            restricted = RESTRICTED_IMPORT_NAMES[root_module]
            for alias in node.names:
                if alias.name in restricted:
                    self.violations.append(f"Import of '{root_module}.{alias.name}' is forbidden in components")
        elif node.names:
            # `from urllib import request` / `from http import client`: the
            # imported name *is* a blocked submodule.
            for alias in node.names:
                if _is_dangerous_submodule(f"{node.module}.{alias.name}"):
                    self.violations.append(f"Import of '{node.module}.{alias.name}' is forbidden in components")

        for alias in node.names:
            if alias.name != "*":
                binding = alias.asname or alias.name
                self._bind_name(binding, frozenset({f"{node.module}.{alias.name}"}))

        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        self.visit(node.value)
        for target in node.targets:
            self.visit(target)
            self._bind_assignment_target(target, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
            self.visit(node.target)
            self._bind_assignment_target(node.target, node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr):
        self.visit(node.value)
        self.visit(node.target)
        self._bind_assignment_target(node.target, node.value)

    def visit_AugAssign(self, node: ast.AugAssign):
        self.visit(node.target)
        self.visit(node.value)
        if isinstance(node.target, ast.Name):
            self._bind_name(node.target.id, frozenset())

    def visit_If(self, node: ast.If):
        """Merge aliases from both possible branches instead of trusting visit order."""
        self.visit(node.test)
        before_branches = self._snapshot_alias_state()
        branch_states: list[_AliasState] = []
        for branch in (node.body, node.orelse):
            self._restore_alias_state(before_branches)
            for statement in branch:
                self.visit(statement)
            branch_states.append(self._snapshot_alias_state())
        self._merge_alias_states(branch_states)

    def _visit_loop(self, node: ast.For | ast.AsyncFor | ast.While) -> None:
        """Merge zero-iteration and loop-body alias states conservatively."""
        before_loop = self._snapshot_alias_state()
        if isinstance(node, ast.While):
            self.visit(node.test)
        else:
            self.visit(node.iter)
            self.visit(node.target)
            self._bind_iterated_target(node.target, node.iter)

        for statement in node.body:
            self.visit(statement)
        after_body = self._snapshot_alias_state()
        self._merge_alias_states([before_loop, after_body])

        if node.orelse:
            before_else = self._snapshot_alias_state()
            for statement in node.orelse:
                self.visit(statement)
            after_else = self._snapshot_alias_state()
            # The else suite is skipped when a loop exits through break.
            self._merge_alias_states([before_else, after_else])

    def visit_For(self, node: ast.For):
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor):
        self._visit_loop(node)

    def visit_While(self, node: ast.While):
        self._visit_loop(node)

    def _visit_comprehension_expression(
        self, generators: list[ast.comprehension], expressions: tuple[ast.AST, ...]
    ) -> None:
        """Visit comprehensions in evaluation order with isolated target bindings."""
        enclosing_state = self._snapshot_alias_state()
        target_names: set[str] = set()
        for generator in generators:
            self.visit(generator.iter)
            self.visit(generator.target)
            self._bind_iterated_target(generator.target, generator.iter)
            target_names.update(self._assignment_target_names(generator.target))
            for condition in generator.ifs:
                self.visit(condition)
        for expression in expressions:
            self.visit(expression)
        self._restore_target_names(target_names, enclosing_state)

    def visit_ListComp(self, node: ast.ListComp):
        self._visit_comprehension_expression(node.generators, (node.elt,))

    def visit_SetComp(self, node: ast.SetComp):
        self._visit_comprehension_expression(node.generators, (node.elt,))

    def visit_DictComp(self, node: ast.DictComp):
        self._visit_comprehension_expression(node.generators, (node.key, node.value))

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        self._visit_comprehension_expression(node.generators, (node.elt,))

    def _shadow_arguments(self, arguments: ast.arguments) -> None:
        positional = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        for argument in positional:
            self._bind_name(argument.arg, frozenset())
        if arguments.vararg:
            self._bind_name(arguments.vararg.arg, frozenset())
        if arguments.kwarg:
            self._bind_name(arguments.kwarg.arg, frozenset())

    def _visit_function_definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Decorators, defaults, and annotations are evaluated in the enclosing
        # scope; the function body receives an isolated alias state.
        for decorator in node.decorator_list:
            self.visit(decorator)
        self.visit(node.args)
        if node.returns:
            self.visit(node.returns)
        for type_parameter in getattr(node, "type_params", ()):
            self.visit(type_parameter)

        enclosing_state = self._snapshot_alias_state()
        self._bind_name(node.name, frozenset())
        self._shadow_arguments(node.args)
        for statement in node.body:
            self.visit(statement)
        self._restore_alias_state(enclosing_state)
        self._bind_name(node.name, frozenset())

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_function_definition(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_function_definition(node)

    def visit_Lambda(self, node: ast.Lambda):
        self.visit(node.args)
        enclosing_state = self._snapshot_alias_state()
        self._shadow_arguments(node.args)
        self.visit(node.body)
        self._restore_alias_state(enclosing_state)

    def visit_ClassDef(self, node: ast.ClassDef):
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword)
        for type_parameter in getattr(node, "type_params", ()):
            self.visit(type_parameter)

        enclosing_state = self._snapshot_alias_state()
        for statement in node.body:
            self.visit(statement)
        self._restore_alias_state(enclosing_state)
        self._bind_name(node.name, frozenset())

    def visit_Attribute(self, node: ast.Attribute):
        """Check attribute access: dunder escapes, os.environ, urllib.request, ..."""
        if node.attr in DANGEROUS_DUNDER_ATTRS:
            self.violations.append(f"Access to '{node.attr}' is forbidden in components (sandbox escape)")
        elif isinstance(node.value, ast.Name):
            for module_name in self._resolved_names(node.value.id):
                violation = next(
                    (
                        message
                        for mod, attr, message in DANGEROUS_ATTRIBUTE_READS
                        if module_name == mod and node.attr == attr
                    ),
                    None,
                )
                if violation:
                    self.violations.append(violation)
                    break
        # Dotted access to a blocked submodule (``urllib.request`` / ``http.client``),
        # which a bare ``import urllib`` / ``import http`` makes reachable at runtime
        # without an explicit submodule import. Alias-resolved on the root name.
        if dotted := self._dangerous_submodule_access(node):
            self.violations.append(f"Access to '{dotted}' is forbidden in components")
        self.generic_visit(node)

    def _resolved_dotted(self, node: ast.Attribute) -> frozenset[str]:
        """Possible dotted names of an attribute chain, with its root alias-resolved."""
        parts = _dotted_parts(node)
        if not parts:
            return frozenset()
        return frozenset(".".join([root, *parts[1:]]) for root in self._resolved_names(parts[0]))

    def _dangerous_submodule_access(self, node: ast.Attribute) -> str | None:
        # Exact match (not prefix): the ``urllib.request`` node itself is visited
        # within ``urllib.request.urlopen``, so matching exactly avoids double-flagging.
        return next((name for name in sorted(self._resolved_dotted(node)) if name in DANGEROUS_SUBMODULES), None)

    def visit_Name(self, node: ast.Name):
        """Catch wildcard-imported reads (``from os import *``; ``environ[...]``)."""
        if isinstance(node.ctx, ast.Load):
            for mod in self.wildcard_modules:
                if node.id in _DANGEROUS_READ_MEMBERS.get(mod, ()):
                    self.violations.append(f"Use of '{node.id}' (via 'from {mod} import *') is forbidden in components")
                    break
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        self._check_name_call(node)
        self._check_attribute_call(node)
        self._check_getattr_access(node)
        self.generic_visit(node)

    def _check_name_call(self, node: ast.Call):
        """Check bare-name calls: builtins (exec) and wildcard-imported members.

        e.g. ``exec(...)`` and, after ``from os import *``, a bare ``dup2(...)``.
        """
        if not isinstance(node.func, ast.Name):
            return
        name = node.func.id
        if name in DANGEROUS_CALLS:
            self.violations.append(DANGEROUS_CALLS[name])
            return
        for mod in self.wildcard_modules:
            if name in _DANGEROUS_CALL_MEMBERS.get(mod, ()):
                self.violations.append(f"Use of '{name}()' (via 'from {mod} import *') is forbidden in components")
                return

    def _check_attribute_call(self, node: ast.Call):
        """Check attribute calls like os.system(), subprocess.run().

        Resolves import aliases so ``import os as o; o.system()`` is caught.
        """
        if not isinstance(node.func, ast.Attribute):
            return
        if not isinstance(node.func.value, ast.Name):
            return

        method_name = node.func.attr

        for module_name in self._resolved_names(node.func.value.id):
            for mod, method, message in DANGEROUS_ATTR_CALLS:
                if module_name == mod and method_name == method:
                    self.violations.append(message)
                    return

    def _check_getattr_access(self, node: ast.Call):
        """Check reflective access to restricted module members.

        ``getattr`` is common in legitimate components, so it stays allowed for
        ordinary objects and safe module attributes. On modules with restricted
        members, a dynamic attribute name is rejected because it could resolve to
        one of those members at runtime.
        """
        if not (
            isinstance(node.func, ast.Name)
            and "getattr" in self._resolved_names(node.func.id)
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            return

        module_names = self._resolved_names(node.args[0].id)
        try:
            attr_node = node.args[1]
        except IndexError:
            return
        if not (isinstance(attr_node, ast.Constant) and isinstance(attr_node.value, str)):
            dangerous_modules = sorted(
                module_name
                for module_name in module_names
                if module_name in _DANGEROUS_CALL_MEMBERS or module_name in _DANGEROUS_READ_MEMBERS
            )
            if dangerous_modules:
                self.violations.append(
                    f"Dynamic getattr() access on module '{dangerous_modules[0]}' is forbidden in components"
                )
            return

        attr_name = attr_node.value
        for mod, attr, message in DANGEROUS_ATTRIBUTE_READS:
            if mod in module_names and attr_name == attr:
                self.violations.append(message)
                return
        for mod, method, message in DANGEROUS_ATTR_CALLS:
            if mod in module_names and attr_name == method:
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

    module_aliases, wildcard_modules = _collect_imports(tree)
    checker = _SecurityChecker(module_aliases=module_aliases, wildcard_modules=wildcard_modules)
    checker.visit(tree)

    return SecurityScanResult(
        is_safe=len(checker.violations) == 0,
        violations=tuple(checker.violations),
    )
