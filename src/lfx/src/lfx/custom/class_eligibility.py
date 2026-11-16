"""Best-effort mistake guard for the component class cache (see ``lfx.custom.class_cache``).

This is NOT a sandbox and does not prove a source is free of shared state; it is easy to bypass on purpose.
The security boundary is the trusted-source gate: only registry sources are ever cached. This guard only
keeps the cache away from patterns that would leak state between builds by accident, because a cached class
outlives one build: class-level mutation, mutable class attributes, dunder tricks, and top-level side effects.
"""

from __future__ import annotations

import ast
import re

# ``inputs``/``outputs`` are deep-copied per instance by Component.__init__, so class-level lists of them are fine.
# Every other class container (``replacement``, ``conditional_paths``, ...) is tracked and declined if mutated.
_PER_INSTANCE = frozenset({"inputs", "outputs"})
# Function/method decorators that cannot cache or share state (``functools.cache`` and friends are declined).
_DECORATORS = frozenset(
    {"staticmethod", "classmethod", "property", "override", "abstractmethod", "contextmanager", "asynccontextmanager"}
)
_ACCESSOR_SUFFIXES = frozenset({"setter", "getter", "deleter"})
_ALLOWED_DUNDERS = frozenset({"__name__", "__doc__"})
_MUTATORS = frozenset(
    {"append", "extend", "insert", "update", "setdefault", "pop", "popitem", "clear", "remove", "add", "discard"}
    | {"difference_update", "intersection_update", "symmetric_difference_update"}
    | {"sort", "reverse", "__setitem__", "__delitem__"}
)
_DUNDER = re.compile(r"^__\w+__$")
# Dunder methods that may be CALLED as ``super().X(...)``. Everything else (``__setattr__``, ``__class__``,
# ``__dict__``, ``__mro__``, ``__thisclass__``, ...) stays forbidden even via ``super()``; no loads or aliases.
_SUPER_CALLABLE = frozenset(
    {"__init__", "__deepcopy__", "__copy__", "__getattr__", "__getstate__", "__setstate__", "__repr__", "__str__"}
)
_LFX_PREFIXES = ("lfx.", "langflow.")


def _is_const(node: ast.AST | None) -> bool:
    return (
        node is None
        or isinstance(node, ast.Constant)
        or (isinstance(node, ast.Tuple) and all(map(_is_const, node.elts)))
    )


def _chain_root(node: ast.AST) -> tuple[ast.AST, str | None]:
    """Return the root of an attribute/subscript chain and the attribute directly on it (``self.x[k]`` -> x)."""
    first = None
    while isinstance(node, ast.Attribute | ast.Subscript):
        if isinstance(node, ast.Attribute):
            first = node.attr
        node = node.value
    return node, first


def _decorator_name(dec: ast.expr) -> str:
    """``classmethod`` for both ``@classmethod`` and ``@builtins.classmethod``; ``""`` for anything else."""
    return dec.id if isinstance(dec, ast.Name) else dec.attr if isinstance(dec, ast.Attribute) else ""


def _decorator_reason(node: ast.FunctionDef | ast.AsyncFunctionDef, rebound: set[str]) -> str | None:
    for dec in node.decorator_list:
        name = _decorator_name(dec)
        accessor = isinstance(dec, ast.Attribute) and name in _ACCESSOR_SUFFIXES
        if not (name in _DECORATORS or accessor):
            return "function_decorator"
        if name in rebound:
            return "rebinds_decorator_name"
    return None


def _default_reason(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> str | None:
    defaults = [*node.args.defaults, *node.args.kw_defaults]
    if all(d is None or _is_const(d) or (isinstance(d, ast.UnaryOp) and _is_const(d.operand)) for d in defaults):
        return None
    return "mutable_default_argument"


def _names(statement: ast.Assign | ast.AnnAssign) -> list[str]:
    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
    return [t.id if isinstance(t, ast.Name) else "" for t in targets]


def _lfx_names(module: ast.Module) -> frozenset[str]:
    """Names imported ``from lfx...``/``from langflow...`` and not rebound anywhere at module level."""
    lfx: set[str] = set()
    other: set[str] = set()
    for st in module.body:
        if isinstance(st, ast.Import | ast.ImportFrom):
            from_lfx = isinstance(st, ast.ImportFrom) and st.level == 0 and (st.module or "").startswith(_LFX_PREFIXES)
            (lfx if from_lfx else other).update(a.asname or a.name.split(".")[0] for a in st.names)
        elif isinstance(st, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            other.add(st.name)
        elif isinstance(st, ast.Assign | ast.AnnAssign):
            other.update(_names(st))
    return frozenset(lfx - other)


def _literal_ok(node: ast.AST | None, lfx: frozenset[str], *, calls: bool = False) -> bool:
    """Constants, lfx names, nested containers, ``+``/``|`` of those, ``frozenset(...)``; optionally lfx calls."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, ast.USub | ast.UAdd) and isinstance(node.operand, ast.Constant)
    if isinstance(node, ast.Name | ast.Attribute):
        root, _ = _chain_root(node) if isinstance(node, ast.Attribute) else (node, None)
        return isinstance(root, ast.Name) and root.id in lfx and not isinstance(node, ast.Subscript)
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return all(_literal_ok(e, lfx, calls=calls) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _literal_ok(k, lfx, calls=calls) for k in node.keys) and all(
            _literal_ok(v, lfx, calls=calls) for v in node.values
        )
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, ast.Add | ast.BitOr) and all(
            _literal_ok(side, lfx, calls=calls) for side in (node.left, node.right)
        )
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        allowed = (calls and node.func.id in lfx) or (node.func.id in {"frozenset", "set"} and not node.keywords)
        return (
            allowed
            and all(_literal_ok(a, lfx, calls=calls) for a in node.args)
            and all(k.arg is not None and _literal_ok(k.value, lfx, calls=calls) for k in node.keywords)
        )
    return False


def _module_reason(statement: ast.stmt, lfx: frozenset[str], containers: set[str]) -> str | None:
    """Reason to decline a module-level statement; names of allowed literal containers go to ``containers``."""
    if isinstance(statement, ast.Import | ast.ImportFrom | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return None
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return None  # docstring
    if isinstance(statement, ast.If):  # only ``if TYPE_CHECKING:`` blocks that import
        guard = isinstance(statement.test, ast.Name) and statement.test.id == "TYPE_CHECKING"
        if guard and not statement.orelse and all(isinstance(s, ast.Import | ast.ImportFrom) for s in statement.body):
            return None
    if isinstance(statement, ast.Assign | ast.AnnAssign):
        names, value = _names(statement), statement.value
        if _is_const(value):
            return None
        if all(names) and _literal_ok(value, lfx):
            containers.update(names)  # fine as long as nothing mutates it; see ``_analyse``
            return None
        return "top_level_assignment"
    return f"top_level_{type(statement).__name__.lower()}"


def _class_reason(node: ast.ClassDef, lfx: frozenset[str], attrs: set[str], components: set[str]) -> str | None:
    """Reason to decline a class; names of allowed container class attributes go to ``attrs``.

    ``inputs``/``outputs`` are exempt only on classes deriving from an lfx/langflow import (or from such a class
    defined earlier), since only ``Component.__init__`` copies them per instance. ``components`` collects those.
    """
    if node.decorator_list or node.keywords:
        return "decorated_class"
    if any(
        (root := _chain_root(base)[0]) and isinstance(root, ast.Name) and root.id in lfx | components
        for base in node.bases
    ):
        components.add(node.name)
    per_instance = _PER_INSTANCE if node.name in components else frozenset()
    for statement in node.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.Pass) or (
            isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
        ):
            continue
        if not isinstance(statement, ast.Assign | ast.AnnAssign):
            return f"class_body_{type(statement).__name__.lower()}"
        names, value = _names(statement), statement.value
        if _is_const(value) or all(name in per_instance for name in names):
            continue
        if not (all(names) and _literal_ok(value, lfx, calls=True)):
            return "mutable_class_attribute"
        attrs.update(names)
    return None


def _mutation_target(node: ast.AST) -> ast.AST | None:
    """The object an attribute/subscript store, ``del``, or mutating method call changes."""
    if isinstance(node, ast.Attribute | ast.Subscript) and isinstance(node.ctx, ast.Store | ast.Del):
        return node
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _MUTATORS:
        return node.func.value
    return None


def _mutates(node: ast.AST, shared: set[str], attrs: set[str] = frozenset()) -> bool:
    """Mutation rooted at a shared name (class, ``cls``, module container) or at ``<anything>.<container attr>``."""
    target = _mutation_target(node)
    if target is None:
        return False
    root, first = _chain_root(target)
    return (isinstance(root, ast.Name) and root.id in shared) or first in attrs


_READ_ONLY_CALLS = frozenset({"len", "list", "tuple", "set", "frozenset", "dict", "sorted", "any", "all", "enumerate"})


def _escapes(node: ast.AST, parent: ast.AST) -> bool:
    """True when a shared container is used other than for indexing, attribute reads, iteration or membership.

    Such uses (``alias = SEEN``, ``return SEEN``, ``helper(SEEN)``) could let it be mutated under another name.
    """
    if isinstance(parent, ast.Subscript | ast.Attribute) and parent.value is node:
        return False
    if isinstance(parent, ast.Compare) or (isinstance(parent, ast.For | ast.comprehension) and parent.iter is node):
        return False
    return not (
        isinstance(parent, ast.Call)
        and node in parent.args
        and isinstance(parent.func, ast.Name)
        and parent.func.id in _READ_ONLY_CALLS
    )


def _alias_reason(module: ast.Module, containers: set[str], attrs: set[str], lfx: frozenset[str]) -> str | None:
    """Decline shared containers escaping inside function bodies (class-body uses are copied per instance).

    Arguments to functions imported from lfx/langflow (reviewed framework helpers) are allowed.
    """
    framework_args = {
        id(arg)
        for call in ast.walk(module)
        if isinstance(call, ast.Call) and isinstance(root := _chain_root(call.func)[0], ast.Name) and root.id in lfx
        for arg in [*call.args, *(k.value for k in call.keywords)]
    }
    for func in ast.walk(module):
        if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        for parent in ast.walk(func):
            for child in ast.iter_child_nodes(parent):
                named = isinstance(child, ast.Name) and child.id in containers
                attribute = isinstance(child, ast.Attribute) and child.attr in attrs
                if (
                    (named or attribute)
                    and isinstance(child.ctx, ast.Load)
                    and id(child) not in framework_args
                    and _escapes(child, parent)
                ):
                    return "shared_container_alias"
    return None


def _analyse(source: str) -> str | None:
    module = ast.parse(source)
    classes = [n for n in module.body if isinstance(n, ast.ClassDef)]
    lfx = _lfx_names(module)
    containers: set[str] = set()
    attrs: set[str] = set()
    components: set[str] = set()
    for statement in module.body:
        if reason := _module_reason(statement, lfx, containers) or (
            _class_reason(statement, lfx, attrs, components) if isinstance(statement, ast.ClassDef) else None
        ):
            return reason
    if reason := _alias_reason(module, containers, attrs, lfx):
        return reason
    functions = ast.FunctionDef | ast.AsyncFunctionDef
    shared = {n.name for n in classes} | {n.name for n in module.body if isinstance(n, functions)} | containers
    classmethod_params = {
        id(f): receivers[0].arg
        for c in classes
        for f in c.body
        if isinstance(f, functions)
        and (receivers := f.args.posonlyargs + f.args.args)
        and any(_decorator_name(d) == "classmethod" for d in f.decorator_list)
    }
    super_calls = {
        id(n.func)
        for n in ast.walk(module)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in _SUPER_CALLABLE
        and isinstance(n.func.value, ast.Call)
        and isinstance(n.func.value.func, ast.Name)
        and n.func.value.func.id == "super"
        and not n.func.value.args
        and not n.func.value.keywords
    }
    rebound = {
        n
        for st in module.body
        if isinstance(st, ast.Assign | ast.AnnAssign | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        for n in (_names(st) if isinstance(st, ast.Assign | ast.AnnAssign) else [st.name])
    }
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            if reason := _default_reason(node):
                return reason
            if not isinstance(node, ast.Lambda) and (reason := _decorator_reason(node, rebound)):
                return reason
        if isinstance(node, ast.Global | ast.Nonlocal):
            return "global_or_nonlocal"
        if (
            isinstance(node, ast.Attribute)
            and _DUNDER.match(node.attr)
            and node.attr not in _ALLOWED_DUNDERS
            and id(node) not in super_calls
        ):
            return "dunder_access"
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _DUNDER.match(node.value):
            return "dunder_string"
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            first_is_self = bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id == "self"
            if name in {"setattr", "delattr"} and not first_is_self:
                return "setattr_on_non_self"
        if _mutates(node, shared, attrs):
            return "class_level_mutation"
        if isinstance(node, functions) and id(node) in classmethod_params:
            cls_name = {classmethod_params[id(node)]}
            if any(_mutates(inner, cls_name) for inner in ast.walk(node)):
                return "class_level_mutation"
    return None


def ineligible_reason(source: str) -> str | None:
    """Return why ``source`` is declined by the guard, or ``None``. Unparseable source is declined."""
    try:
        return _analyse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return "unparseable"
    except Exception:  # noqa: BLE001  # a guard bug must decline the source, never break the build path
        return "guard_error"
