"""Decide whether ``create_class`` can build a component class once instead of twice.

``prepare_global_scope`` executes a source's module-level definitions in order,
and ``create_class`` then compiles and executes the component class again after
all of them, keeping that second class. The first class is thrown away, so it
can be skipped whenever nothing in the source could have seen it. The check is
static, conservative and cached per exact source text; when it fails, the class
is built twice as before.

This lives outside ``validate`` because that module's globals are copied into
every component's namespace.
"""

from __future__ import annotations

import ast
import hashlib
import threading
from typing import TYPE_CHECKING

from cachetools import LRUCache

if TYPE_CHECKING:
    from collections.abc import Iterator

# Builtins and attributes that read or run code against a module namespace.
_NAMESPACE_ACCESS = frozenset(
    {
        "globals",
        "locals",
        "vars",
        "dir",
        "eval",
        "exec",
        "__globals__",
        "f_globals",
        "f_locals",
        "f_back",
        "_getframe",
        "currentframe",
    }
)
# Methods Python calls by itself while it creates a class.
_CLASS_CREATION_HOOKS = frozenset({"__init_subclass__", "__set_name__"})
_DEFINITION_TYPES = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign, ast.AnnAssign)

_DECISIONS_MAX_ENTRIES = 1024
_DECISIONS: LRUCache[tuple[bytes, str], bool] = LRUCache(maxsize=_DECISIONS_MAX_ENTRIES)
_DECISIONS_LOCK = threading.Lock()


def component_class_builds_once(source: str, module: ast.Module, class_name: str) -> bool:
    """Return whether ``create_class`` may build ``class_name`` only once.

    ``module`` must be the tree ``create_class`` executes for ``source``. The
    answer depends only on that tree, so it is computed once per exact source
    text and class name.
    """
    key = (hashlib.sha256(source.encode("utf-8", "surrogatepass")).digest(), class_name)
    with _DECISIONS_LOCK:
        decision = _DECISIONS.get(key)
    if decision is None:
        definitions = [node for node in module.body if isinstance(node, _DEFINITION_TYPES)]
        decision = first_build_is_unobserved(definitions, class_name)
        with _DECISIONS_LOCK:
            _DECISIONS[key] = decision
    return decision


def first_build_is_unobserved(definitions: list[ast.stmt], class_name: str) -> bool:
    """Return whether nothing in ``definitions`` can see the first, discarded build of ``class_name``.

    Building only the second class gives the same result unless something can
    see the first. This returns False, so both builds stay, when:

    - more than one class has the name, or the class has decorators or keywords;
    - any class in the source defines a class-creation hook or keywords;
    - another definition names the class, mentions it as a string, or reads the
      module namespace (``globals()``, frames, ``eval``);
    - the code that runs while the class is created (bases, class body,
      decorators, defaults and any function they refer to) names the class,
      reads the module namespace, or uses a name that is defined only further
      down the source (it was undefined during the first build).
    """
    targets = [node for node in definitions if isinstance(node, ast.ClassDef) and node.name == class_name]
    if len(targets) != 1 or targets[0].decorator_list or targets[0].keywords:
        return False
    target = targets[0]
    position = next(index for index, node in enumerate(definitions) if node is target)
    functions: dict[str, list[ast.AST]] = {}
    for definition in definitions:
        if definition is target:
            continue
        if isinstance(definition, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.setdefault(definition.name, []).append(definition)
        for node in ast.walk(definition):
            if (
                _has_class_creation_hook(node)
                or (isinstance(node, ast.Name) and (node.id == class_name or node.id in _NAMESPACE_ACCESS))
                or (isinstance(node, ast.Attribute) and (node.attr == class_name or node.attr in _NAMESPACE_ACCESS))
                or (isinstance(node, ast.Constant) and node.value == class_name)
            ):
                return False
    for member in target.body:
        if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.setdefault(member.name, []).append(member)
    later_names = set().union(*(_bound_names(node) for node in definitions[position + 1 :]))

    pending: list[ast.AST] = [target]
    followed: set[int] = set()
    while pending:
        for node in _runs_at_definition(pending.pop()):
            if isinstance(node, ast.Name):
                if node.id == class_name or node.id in _NAMESPACE_ACCESS or node.id in later_names:
                    return False
                for function in functions.get(node.id, ()):
                    if id(function) not in followed:
                        followed.add(id(function))
                        pending.extend(function.body)
            elif isinstance(node, ast.Attribute):
                if node.attr == class_name or node.attr in _NAMESPACE_ACCESS:
                    return False
            elif node is not target and _has_class_creation_hook(node):
                return False
    return True


def _has_class_creation_hook(node: ast.AST) -> bool:
    return isinstance(node, ast.ClassDef) and (
        bool(node.keywords)
        or any(
            isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef) and member.name in _CLASS_CREATION_HOOKS
            for member in node.body
        )
    )


def _runs_at_definition(node: ast.AST) -> Iterator[ast.AST]:
    """Yield the nodes that execute when ``node`` is defined: everything except function bodies."""
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            pending.extend(current.decorator_list)
            pending.extend(current.args.defaults)
            pending.extend(default for default in current.args.kw_defaults if default is not None)
        else:
            pending.extend(ast.iter_child_nodes(current))


def _bound_names(definition: ast.stmt) -> set[str]:
    if isinstance(definition, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
        return {definition.name}
    targets = definition.targets if isinstance(definition, ast.Assign) else [definition.target]
    return {node.id for target in targets for node in ast.walk(target) if isinstance(node, ast.Name)}
