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
  (``gen.gi_frame.f_back.f_globals``). It also rejects ``str.format`` /
  ``str.format_map`` and the lower-level formatter sinks (``string.Formatter`` traversal
  primitives, ``operator.attrgetter`` and ``operator.methodcaller``) because replacement
  fields / dotted paths / deferred method names are evaluated at runtime and can traverse
  attributes that are invisible to the AST, and it rejects literal replacement-field
  templates that reach into a dunder regardless of which formatter ultimately consumes
  them.
* :func:`import_allowed_module` wraps each allow-listed module in :class:`_ModuleProxy`
  before it is injected into the exec globals. Module-granularity trust is unsound in
  Python: a module object transitively exposes its entire import graph through ordinary
  public attributes, so e.g. ``json.codecs.sys.modules["os"]`` (also ``re.enum.sys``,
  ``typing.sys``, ``numpy.sys``) reaches the host ``os`` module without tripping the AST
  gate or the dunder wildcard. The proxy refuses underscore-prefixed attributes and the
  names in ``_BLOCKED_MODULE_ATTRIBUTES``, and recursively re-wraps sub-module
  attributes, so no real module object (and no path to ``sys.modules``) ever enters the
  sandbox.

This is defense-in-depth, NOT a guaranteed sandbox — Python sandboxing is notoriously
hard and determined attackers may still find gadgets. The primary control for untrusted
access is authentication: do not expose an instance with ``LANGFLOW_AUTO_LOGIN=true`` on
an untrusted network.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import re
import types

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
        "format",
        "format_map",
        # ``str.format``/``format_map`` are not the only formatter sinks: the same
        # dunder-traversal lives in a *string* argument (invisible to the AST attribute
        # check) when fed through the lower-level ``string.Formatter`` primitives or
        # ``operator.attrgetter``. Block the method names so e.g.
        # ``string.Formatter().vformat("{0.__globals__[os]...}", (f,), {})``,
        # ``Formatter().get_field("0.__globals__...", (f,), {})`` and
        # ``operator.attrgetter("__globals__")(f)`` are rejected as ast.Attribute.
        "vformat",
        "get_field",
        "get_value",
        "format_field",
        "convert_field",
        "attrgetter",
        # ``operator.methodcaller`` defers a method *name* (a runtime string) to call
        # time, so it reaches the same sinks invisibly to the AST: a runtime-assembled
        # template defeats the ``_FORMAT_FIELD_DUNDER_RE`` literal scan, and
        # ``methodcaller("format", f)(tmpl)`` (== ``tmpl.format(f)``) /
        # ``methodcaller("format_map", d)(tmpl)`` carry the dunder chain in ``tmpl``.
        # More generally ``methodcaller("__getattribute__", "__globals__")(f)`` would
        # bypass the dunder-attribute check entirely, so block the factory by name.
        # (``operator.itemgetter`` is intentionally NOT blocked: it only performs
        # subscription, cannot do the attribute traversal needed to bootstrap an escape,
        # and is common in legitimate data code.)
        "methodcaller",
        "mro",  # int.mro() reaches the object hierarchy without a dunder attribute
    }
)

# Matches a dunder reached inside a str.format()/Formatter replacement field, e.g.
# "{0.__globals__}" or "{0[__builtins__]}". Such traversals live inside a literal
# template string and are invisible to the AST attribute check below, so a literal
# dunder-bearing template is rejected regardless of which formatter consumes it.
_FORMAT_FIELD_DUNDER_RE = re.compile(r"\{[^{}]*__")

# Attribute names through which an allow-listed module transitively exposes the
# interpreter's module system or host-powerful modules. A real module object exposes
# its entire import graph as ordinary public attributes — json.codecs.sys, re.enum.sys,
# typing.sys and numpy.sys all bind ``sys`` at top level, and from there
# ``sys.modules["os"]`` is a one-step direct hit. These chains use no dunder and no
# blocked AST attribute, so the gate cannot see them; _ModuleProxy refuses these names
# instead. Note this intentionally does NOT block the top-level allow-listed module
# itself: allow-listing ``os`` in Global Imports remains an explicit (trusted) admin
# choice — what is closed here is *transitive* exposure through an unrelated module.
_BLOCKED_MODULE_ATTRIBUTES = frozenset(
    {
        # Module system / interpreter internals: reaching these reaches sys.modules.
        "sys",
        "modules",
        "builtins",
        "importlib",
        "loader",
        "spec",
        "meta_path",
        "path_hooks",
        "find_spec",
        "find_module",
        "load_module",
        "exec_module",
        "create_module",
        "module_from_spec",
        "builtin_module_names",
        "runpy",
        "inspect",
        "gc",
        # Host-powerful stdlib modules frequently bound transitively: os.system /
        # subprocess / ctypes are RCE; shutil / pathlib / io / socket read or write the
        # host filesystem and network with the server process's privileges.
        "os",
        "subprocess",
        "ctypes",
        # numpy.ctypeslib.load_library(...) loads arbitrary native libraries and hands
        # out callable C functions (e.g. libc.system) even though ``ctypes`` itself is
        # blocked; ``ctypeslib`` is a public sub-module attribute on numpy.
        "ctypeslib",
        "shutil",
        "pathlib",
        "io",
        "socket",
        # Named by the report's PoC chains: json.codecs.sys, re.enum.sys.
        "codecs",
        "enum",
    }
)


class _ModuleProxy:
    """Read-only, attribute-filtering proxy for an allow-listed module.

    Injecting the real module object into the exec globals exposes its transitive
    import graph through public attributes (``json.codecs.sys.modules["os"]``),
    bypassing the AST gate and restricted builtins. The sandbox receives this proxy
    instead: dunder/underscore-prefixed attributes and the names in
    ``_BLOCKED_MODULE_ATTRIBUTES`` are refused, and sub-module attributes are
    recursively re-wrapped, so no real module object ever enters the sandbox.

    ``__getattribute__`` (not ``__getattr__``) is overridden so the internal
    ``_module`` slot is unreachable from sandboxed code as well.
    """

    def __init__(self, module: types.ModuleType) -> None:
        object.__setattr__(self, "_module", module)

    def __getattribute__(self, name: str):
        if name.startswith("_") or name in _BLOCKED_MODULE_ATTRIBUTES:
            msg = f"Access to attribute '{name}' is not allowed."
            raise AttributeError(msg)
        module = object.__getattribute__(self, "_module")
        value = getattr(module, name)
        if isinstance(value, types.ModuleType):
            return _ModuleProxy(value)
        return value

    def __setattr__(self, name: str, value) -> None:
        msg = "Allow-listed modules are read-only in the Python Interpreter."
        raise AttributeError(msg)

    def __delattr__(self, name: str) -> None:
        msg = "Allow-listed modules are read-only in the Python Interpreter."
        raise AttributeError(msg)

    def __repr__(self) -> str:
        module = object.__getattribute__(self, "_module")
        return f"<sandboxed module {module.__name__!r}>"


def import_allowed_module(name: str) -> tuple[str, _ModuleProxy]:
    """Import an allow-listed module and return ``(module_name, sandbox-safe proxy)``.

    Args:
        name: Dotted module name from the Global Imports allow-list.

    Returns:
        The imported module's ``__name__`` (the globals key) and a ``_ModuleProxy``
        wrapping the module so its transitive import graph stays out of the sandbox.

    Raises:
        ImportError: If the module cannot be imported.
    """
    module = importlib.import_module(name)
    return module.__name__, _ModuleProxy(module)


class CodeExecutionDisabledError(ValueError):
    """Raised when code-execution components are disabled by policy.

    Subclasses ``ValueError`` so existing ``except ValueError``/``except Exception``
    handlers around the interpreter components surface the message gracefully.
    """


def ensure_code_execution_enabled() -> None:
    """Refuse to run Python code when either server code-execution policy disables it.

    Registered code-execution components run user- or model-supplied Python. They honor
    both ``allow_custom_components`` and ``block_code_interpreter_components`` so a
    component cannot bypass either policy through direct or tool-mode execution.

    Failure handling is deliberately asymmetric so the gate can never be
    silently bypassed:

    * ``ImportError`` importing the services layer means there is no settings
      stack at all (e.g. a stripped-down lfx embedding). That context is local
      and trusted, so execution is allowed.
    * Any other exception from ``get_settings_service()`` propagates — a stack
      that exists but errors must not fail open.
    * A ``None`` settings service means the stack is registered but failed to
      initialise (``get_service`` swallows init errors into ``None``). Fail
      closed, matching ``validate_flow_for_current_settings``, rather than
      bypass the very control this gate enforces.
    """
    try:
        from lfx.services.deps import get_settings_service
    except ImportError:
        # Services layer absent (e.g. stripped-down lfx embed) -> local/trusted, allow.
        return
    # Resolver failures, including ImportError from inside the settings stack, must
    # propagate rather than masquerade as an absent services layer and fail open.
    settings_service = get_settings_service()
    if settings_service is None:
        # Registered-but-failed settings stack (get_service swallows init errors into
        # None). Fail closed rather than bypass the gate (GHSA-8qpj-27x8-pwpq).
        msg = (
            "Python code execution is disabled because the settings service could not "
            "be resolved. Check the server configuration and try again."
        )
        raise CodeExecutionDisabledError(msg)
    if not getattr(settings_service.settings, "allow_custom_components", True):
        msg = (
            "Python code execution is disabled because allow_custom_components is False. "
            "Set LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true to enable this component."
        )
        raise CodeExecutionDisabledError(msg)
    if getattr(settings_service.settings, "block_code_interpreter_components", False):
        msg = (
            "Python code execution is disabled because block_code_interpreter_components is True. "
            "Set LANGFLOW_BLOCK_CODE_INTERPRETER_COMPONENTS=false to enable this component."
        )
        raise CodeExecutionDisabledError(msg)


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
    (dunder attribute traversal, formatter traversal, and frame introspection) and
    inline imports.

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
            # Blocks "{0.__globals__}" style traversal that the AST attribute check cannot
            # see because the attribute chain lives inside a literal string. Catches the
            # template regardless of which formatter (str.format, Formatter.vformat, ...)
            # ultimately consumes it.
            msg = "Access to dunder attributes via format strings is not allowed."
            raise ValueError(msg)
