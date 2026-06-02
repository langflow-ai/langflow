"""Best-effort hardening for the Python Interpreter / Python REPL components.

These components execute user-supplied code via ``exec`` (through
``langchain_experimental``'s ``PythonREPL``). Historically the globals dict passed to
``exec`` contained only the allow-listed modules and never set ``__builtins__``;
CPython then auto-injects the *full* builtins module, so ``__import__``, ``open``,
``eval``, ``exec`` and the entire import machinery stayed reachable regardless of the
"Global Imports" allow-list. The allow-list looked like a sandbox but was silently
bypassable (e.g. ``__import__("subprocess").check_output(["id"])``).

This module restricts that environment:

* :func:`safe_builtins` returns a curated ``__builtins__`` mapping that keeps the common
  safe builtins (``print``, ``len``, ``range``, container/number types, exceptions, ...)
  but removes anything that can import modules, execute/compile code, read the
  filesystem, or reach interpreter internals (``__import__``, ``eval``, ``exec``,
  ``compile``, ``open``, ``input``, ``globals``/``locals``/``vars``,
  ``getattr``/``setattr``/``delattr``, ``breakpoint``, ...).
* :func:`validate_code_safety` rejects code that bypasses the allow-list with an inline
  ``import`` or reaches the classic builtin-free escape gadgets: dunder attribute access
  (``().__class__.__subclasses__()``) and frame/traceback introspection
  (``gen.gi_frame.f_back.f_globals``).

This is defense-in-depth, NOT a guaranteed sandbox — Python sandboxing is notoriously
hard and determined attackers may still find gadgets. The primary control for untrusted
access is authentication: do not expose an instance with ``LANGFLOW_AUTO_LOGIN=true`` on
an untrusted network.
"""

from __future__ import annotations

import ast
import builtins
import re

# Builtins considered safe to expose to interpreter code. Deliberately excludes anything
# that can import modules, execute/compile code, touch the filesystem, or reach
# interpreter internals. Names absent here resolve to NameError inside the interpreter,
# which is what makes the "Global Imports" allow-list the only way to bring in modules.
_SAFE_BUILTIN_NAMES = frozenset(
    {
        "abs",
        "aiter",
        "anext",
        "all",
        "any",
        "ascii",
        "bin",
        "bool",
        "bytearray",
        "bytes",
        "callable",
        "chr",
        "complex",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "hasattr",
        "hash",
        "hex",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "oct",
        "ord",
        "pow",
        "print",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "type",
        "zip",
        # Exception hierarchy so try/except and explicit raises behave normally.
        "ArithmeticError",
        "AssertionError",
        "AttributeError",
        "BaseException",
        "Exception",
        "FloatingPointError",
        "IndexError",
        "KeyError",
        "KeyboardInterrupt",
        "LookupError",
        "NameError",
        "NotImplementedError",
        "OverflowError",
        "RecursionError",
        "RuntimeError",
        "StopIteration",
        "TypeError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "ValueError",
        "ZeroDivisionError",
    }
)

# Attribute names that expose interpreter internals or sandbox-escape gadgets even
# without any dangerous builtin. Dunder attributes (``__class__``, ``__subclasses__``,
# ``__globals__``, ``__mro__``, ``__builtins__``, ...) are handled generically; this set
# covers the non-dunder frame / coroutine / traceback introspection attributes.
_BLOCKED_ATTRIBUTES = frozenset(
    {
        "gi_frame",
        "gi_code",
        "cr_frame",
        "cr_code",
        "ag_frame",
        "ag_code",
        "f_globals",
        "f_locals",
        "f_builtins",
        "f_back",
        "f_code",
        "f_trace",
        "tb_frame",
        "tb_next",
        "func_globals",
        "func_code",
        "__dict__",
        "mro",  # int.mro() reaches the object hierarchy without a dunder attribute
    }
)

# Matches a str.format()/format_map() replacement field that reaches into a dunder
# attribute or item (e.g. "{0.__globals__}", "{0[__builtins__]}"). Such traversals live
# inside the template string and are invisible to the AST attribute check below.
_FORMAT_FIELD_DUNDER_RE = re.compile(r"\{[^{}]*__")


def safe_builtins() -> dict:
    """Return a fresh curated ``__builtins__`` mapping for interpreter globals.

    A new dict is returned on each call so callers cannot mutate shared state.
    """
    return {name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES if hasattr(builtins, name)}


def _is_blocked_attribute(attr: str) -> bool:
    """Return True if attribute access to ``attr`` should be rejected."""
    # Dunder attributes are the classic escape gadgets; the explicit set covers
    # frame/traceback introspection attributes that are not dunders.
    return attr.startswith("__") or attr in _BLOCKED_ATTRIBUTES


def validate_code_safety(code: str) -> None:
    """Reject code that bypasses the import allow-list or reaches escape gadgets.

    This complements :func:`safe_builtins`: restricted builtins stop ``__import__`` /
    ``open`` / ``eval`` etc., while this AST check stops the builtin-free escapes
    (dunder attribute traversal and frame introspection) and inline imports.

    Args:
        code: The Python source to be executed.

    Raises:
        ValueError: If the code performs an inline import or accesses a blocked attribute.
        SyntaxError: If the code cannot be parsed (surfaced to the caller as-is).
    """
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            msg = "Imports are not allowed in the code; declare modules in the Global Imports field instead."
            raise ValueError(msg)  # noqa: TRY004 -- forbidden construct, not an argument type error
        if isinstance(node, ast.Attribute) and _is_blocked_attribute(node.attr):
            msg = f"Access to attribute '{node.attr}' is not allowed."
            raise ValueError(msg)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _FORMAT_FIELD_DUNDER_RE.search(node.value)
        ):
            # Blocks str.format("{0.__globals__}") style traversal that the AST attribute
            # check cannot see because the attribute chain is inside a literal string.
            msg = "Access to dunder attributes via format strings is not allowed."
            raise ValueError(msg)
