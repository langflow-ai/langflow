import ast
import contextlib
import importlib
import sys
import warnings
from types import FunctionType

from pydantic import ValidationError

from lfx.log.logger import logger

_LANGFLOW_IS_INSTALLED = False

with contextlib.suppress(ImportError):
    import langflow  # noqa: F401

    _LANGFLOW_IS_INSTALLED = True


# Migration aid: maps lfx names that *used* to be auto-injected into custom-
# component scope (via the now-removed DEFAULT_IMPORT_STRING preamble) to the
# module the user should import them from. Consulted only by the NameError
# handler in ``create_class`` to produce an actionable hint. Pure static data
# — never exec'd, no langchain/lfx imports triggered, zero cold-start cost.
_LEGACY_LFX_IMPORT_HINTS: dict[str, str] = {
    # lfx.io inputs/outputs
    "BoolInput": "lfx.io",
    "CodeInput": "lfx.io",
    "DataInput": "lfx.io",
    "DictInput": "lfx.io",
    "DropdownInput": "lfx.io",
    "FileInput": "lfx.io",
    "FloatInput": "lfx.io",
    "HandleInput": "lfx.io",
    "IntInput": "lfx.io",
    "JSONInput": "lfx.io",
    "LinkInput": "lfx.io",
    "MessageInput": "lfx.io",
    "MessageTextInput": "lfx.io",
    "MultilineInput": "lfx.io",
    "MultilineSecretInput": "lfx.io",  # pragma: allowlist secret
    "MultiselectInput": "lfx.io",
    "NestedDictInput": "lfx.io",
    "Output": "lfx.io",
    "PromptInput": "lfx.io",
    "SecretStrInput": "lfx.io",  # pragma: allowlist secret
    "SliderInput": "lfx.io",
    "StrInput": "lfx.io",
    "TableInput": "lfx.io",
    # lfx.schema
    "Data": "lfx.schema.data",
    "JSON": "lfx.schema.data",
    "DataFrame": "lfx.schema.dataframe",
    "Table": "lfx.schema.dataframe",
}


def _resolve_import_module_for_name(missing: str | None) -> str | None:
    """Return the module string a missing symbol should be imported from, if known.

    Checks the legacy lfx hint table first, then falls back to the langchain
    symbol table. The langchain lookup is lazy so the field-typing names module
    doesn't get pulled at import time on the hot path; this helper is only
    called from the cold error path.
    """
    if not missing:
        return None
    module = _LEGACY_LFX_IMPORT_HINTS.get(missing)
    if module is not None:
        return module
    from lfx.field_typing.names import LANGCHAIN_SYMBOLS

    symbol = LANGCHAIN_SYMBOLS.get(missing)
    if symbol is not None:
        return symbol[0]
    return None


def _format_undefined_name_message(missing: str | None, original: str) -> str:
    """Format the user-facing NameError message with an actionable hint when possible.

    Used by both the runtime NameError handler in :func:`create_class` and the
    static analysis pass that walks function bodies, so both error paths phrase
    the fix the same way.
    """
    module = _resolve_import_module_for_name(missing)
    hint = (
        f" If not already imported, add `from {module} import {missing}` to your "
        f"component code; if already imported, verify that '{module}' is installed "
        f"and importable in this environment."
        if module
        else ""
    )
    return f"Name error (possibly undefined variable): {original}.{hint}"


def _check_function_body_name_resolution(module: ast.Module, exec_globals: dict) -> None:
    """Static check: undefined symbols inside def-body code that exec(module) doesn't catch.

    Compiling a class body succeeds whether or not its method bodies reference
    real names — Python only resolves Name nodes at call time. The hint
    formatter therefore only fires for class-body references when create_class
    relies on the runtime NameError path. This pass walks every FunctionDef /
    AsyncFunctionDef inside every ClassDef in the parsed module and raises a
    ValueError (with the same actionable hint as the runtime path) when it
    finds a free Name reference that is not in:

      - the module's exec_globals (imports + class/function defs),
      - the function's own locals (parameters, assignments, for/with targets,
        comprehension iterators, except-as bindings, nested defs),
      - Python builtins,
      - the legacy/langchain hint tables.

    The legacy/hint check is intentional: a symbol covered by the hint table is
    almost certainly a missing import the user should be told about (the whole
    point of the hint), so we DO surface it even if it would otherwise look
    like a free name. Names with no hint are passed through silently to avoid
    flagging dynamic/runtime-injected references.
    """
    import builtins as _builtins

    builtin_names = set(dir(_builtins))

    def _collect_target_names(node: ast.AST, out: set[str]) -> None:
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                _collect_target_names(elt, out)
        elif isinstance(node, ast.Starred):
            _collect_target_names(node.value, out)

    def _function_locals(fn: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> set[str]:
        locals_: set[str] = set()
        args = fn.args
        for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            locals_.add(a.arg)
        if args.vararg:
            locals_.add(args.vararg.arg)
        if args.kwarg:
            locals_.add(args.kwarg.arg)
        body = fn.body if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) else [fn.body]
        for sub in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(sub, ast.Assign):
                for tgt in sub.targets:
                    _collect_target_names(tgt, locals_)
            elif isinstance(sub, (ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor)):
                _collect_target_names(sub.target, locals_)
            elif isinstance(sub, (ast.With, ast.AsyncWith)):
                for item in sub.items:
                    if item.optional_vars is not None:
                        _collect_target_names(item.optional_vars, locals_)
            elif (isinstance(sub, ast.ExceptHandler) and sub.name) or isinstance(
                sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                locals_.add(sub.name)
            elif isinstance(sub, ast.Import):
                for alias in sub.names:
                    locals_.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(sub, ast.ImportFrom):
                for alias in sub.names:
                    if alias.name != "*":
                        locals_.add(alias.asname or alias.name)
            elif isinstance(sub, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                for gen in sub.generators:
                    _collect_target_names(gen.target, locals_)
            elif isinstance(sub, ast.NamedExpr):
                # Walrus operator (`if (Tool := load_tool()):`) introduces a
                # new binding in the enclosing function scope. Without this,
                # a walrus-assigned name that happens to live in the hint
                # table (e.g. ``Tool``) would false-positive.
                _collect_target_names(sub.target, locals_)
        return locals_

    def _check_fn(fn: ast.FunctionDef | ast.AsyncFunctionDef, outer_visible: set[str]) -> None:
        """Recurse into a function body, checking Name(Load) refs against the visible scope.

        ``outer_visible`` is the union of names visible from enclosing scopes
        (module globals + each enclosing function's locals). The function's own
        locals_ extend that set for the body walk. Nested function definitions
        recurse with their own (outer | self) visible set so their parameters
        and locals don't false-positive against the caller's scope, and the
        caller's locals don't shadow the nested function's lookup.
        """
        own_locals = _function_locals(fn)
        visible = outer_visible | own_locals

        # Walk only the function's direct body, descending into nested defs
        # via explicit recursion instead of flat-walking — otherwise a Name
        # reference inside a nested function would be checked against the
        # outer function's locals and miss the nested function's own params.
        def _visit(node: ast.AST) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _check_fn(child, visible)
                    continue
                if isinstance(child, ast.Lambda):
                    # Lambdas have their own scope; the parameters belong to
                    # the lambda body only. Construct a synthetic FunctionDef
                    # locals_ from the lambda's args.
                    lambda_locals: set[str] = set()
                    for a in (*child.args.posonlyargs, *child.args.args, *child.args.kwonlyargs):
                        lambda_locals.add(a.arg)
                    if child.args.vararg:
                        lambda_locals.add(child.args.vararg.arg)
                    if child.args.kwarg:
                        lambda_locals.add(child.args.kwarg.arg)
                    lambda_visible = visible | lambda_locals
                    for sub in ast.walk(child.body):
                        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                            _maybe_flag(sub.id, lambda_visible)
                    continue
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    _maybe_flag(child.id, visible)
                _visit(child)

        for stmt in fn.body:
            # Top-level nested defs in this function's body. Skip _visit (which
            # would treat the def's body items as direct children of fn) and
            # recurse with the nested function's own (visible | self) scope.
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _check_fn(stmt, visible)
                continue
            _visit(stmt)

    def _maybe_flag(name: str, visible: set[str]) -> None:
        if name in visible or name in builtin_names:
            return
        # Only surface the typed hint when we actually know which module the
        # missing name should come from. Names without a known import target
        # are deliberately passed through: they may be runtime-injected
        # globals (graph-level context, monkey-patched bases, etc.) and we
        # don't want to false-positive on those.
        if _resolve_import_module_for_name(name) is None:
            return
        msg = _format_undefined_name_message(name, f"name '{name}' is not defined")
        raise ValueError(msg)

    module_visible = set(exec_globals)
    for class_node in (n for n in module.body if isinstance(n, ast.ClassDef)):
        # Names assigned at the class body level (e.g. `outputs = [...]`) are
        # visible inside method bodies via the implicit `self.outputs` and
        # also via plain name lookup during class-body exec. Add them to the
        # visible set so methods referencing them don't false-positive.
        class_visible = module_visible | {
            tgt.id
            for stmt in class_node.body
            if isinstance(stmt, ast.Assign)
            for tgt in stmt.targets
            if isinstance(tgt, ast.Name)
        }
        for fn in (n for n in class_node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            _check_fn(fn, class_visible)


def add_type_ignores() -> None:
    if not hasattr(ast, "TypeIgnore"):

        class TypeIgnore(ast.AST):
            _fields = ()

        ast.TypeIgnore = TypeIgnore  # type: ignore[assignment, misc]


def validate_code(code):
    # Initialize the errors dictionary
    errors = {"imports": {"errors": []}, "function": {"errors": []}}

    # Parse the code string into an abstract syntax tree (AST)
    try:
        tree = ast.parse(code)
    except Exception as e:  # noqa: BLE001
        if hasattr(logger, "opt"):
            logger.debug("Error parsing code", exc_info=True)
        else:
            logger.debug("Error parsing code")
        errors["function"]["errors"].append(str(e))
        return errors

    # Add a dummy type_ignores field to the AST
    add_type_ignores()
    tree.type_ignores = []

    # Evaluate the import statements
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    importlib.import_module(alias.name)
                except ModuleNotFoundError as e:
                    errors["imports"]["errors"].append(str(e))

    # Evaluate the function definition with langflow context
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            code_obj = compile(ast.Module(body=[node], type_ignores=[]), "<string>", "exec")
            try:
                # Create execution context with common langflow imports
                exec_globals = _create_langflow_execution_context()
                exec(code_obj, exec_globals)
            except Exception as e:  # noqa: BLE001
                logger.debug("Error executing function code", exc_info=True)
                errors["function"]["errors"].append(str(e))

    # Return the errors dictionary
    return errors


def _create_langflow_execution_context():
    """Create execution context with common langflow imports."""
    context = {}

    # Import common langflow types that are used in templates
    try:
        from lfx.schema.dataframe import DataFrame

        context["DataFrame"] = DataFrame
    except ImportError:
        # Create a mock DataFrame if import fails
        context["DataFrame"] = type("DataFrame", (), {})

    try:
        from lfx.schema.message import Message

        context["Message"] = Message
    except ImportError:
        context["Message"] = type("Message", (), {})

    try:
        from lfx.schema.data import Data

        context["Data"] = Data
    except ImportError:
        context["Data"] = type("Data", (), {})

    try:
        from lfx.custom import Component

        context["Component"] = Component
    except ImportError:
        context["Component"] = type("Component", (), {})

    try:
        from lfx.io import HandleInput, Output, TabInput

        context["HandleInput"] = HandleInput
        context["Output"] = Output
        context["TabInput"] = TabInput
    except ImportError:
        context["HandleInput"] = type("HandleInput", (), {})
        context["Output"] = type("Output", (), {})
        context["TabInput"] = type("TabInput", (), {})

    # Add common Python typing imports
    try:
        from typing import Any, Optional, Union

        context["Any"] = Any
        context["Dict"] = dict
        context["List"] = list
        context["Optional"] = Optional
        context["Union"] = Union
    except ImportError:
        pass

    return context


def eval_function(function_string: str):
    # Create an empty dictionary to serve as a separate namespace
    namespace: dict = {}

    # Execute the code string in the new namespace
    exec(function_string, namespace)
    function_object = next(
        (
            obj
            for name, obj in namespace.items()
            if isinstance(obj, FunctionType) and obj.__code__.co_filename == "<string>"
        ),
        None,
    )
    if function_object is None:
        msg = "Function string does not contain a function"
        raise ValueError(msg)
    return function_object


def execute_function(code, function_name, *args, **kwargs):
    add_type_ignores()

    module = ast.parse(code)
    exec_globals = globals().copy()

    for node in module.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    imported = importlib.import_module(alias.name)
                    if alias.asname:
                        variable_name = alias.asname
                        exec_globals[variable_name] = imported
                    else:
                        variable_name = alias.name.split(".")[0]
                        exec_globals[variable_name] = sys.modules.get(variable_name, imported)
                except ModuleNotFoundError as e:
                    msg = f"Module {alias.name} not found. Please install it and try again."
                    raise ModuleNotFoundError(msg) from e

    function_code = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    function_code.parent = None
    code_obj = compile(ast.Module(body=[function_code], type_ignores=[]), "<string>", "exec")
    exec_locals = dict(locals())
    try:
        exec(code_obj, exec_globals, exec_locals)
    except Exception as exc:
        msg = "Function string does not contain a function"
        raise ValueError(msg) from exc

    # Add the function to the exec_globals dictionary
    exec_globals[function_name] = exec_locals[function_name]

    return exec_globals[function_name](*args, **kwargs)


def create_function(code, function_name):
    if not hasattr(ast, "TypeIgnore"):

        class TypeIgnore(ast.AST):
            _fields = ()

        ast.TypeIgnore = TypeIgnore

    module = ast.parse(code)
    exec_globals = globals().copy()

    for node in module.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            for alias in node.names:
                try:
                    if isinstance(node, ast.ImportFrom):
                        module_name = node.module
                        exec_globals[alias.asname or alias.name] = getattr(
                            importlib.import_module(module_name), alias.name
                        )
                    else:
                        module_name = alias.name
                        imported = importlib.import_module(module_name)
                        if alias.asname:
                            exec_globals[alias.asname] = imported
                        else:
                            top_level = module_name.split(".")[0]
                            exec_globals[top_level] = sys.modules.get(top_level, imported)
                except ModuleNotFoundError as e:
                    msg = f"Module {alias.name} not found. Please install it and try again."
                    raise ModuleNotFoundError(msg) from e

    function_code = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    function_code.parent = None
    code_obj = compile(ast.Module(body=[function_code], type_ignores=[]), "<string>", "exec")
    exec_locals = dict(locals())
    with contextlib.suppress(Exception):
        exec(code_obj, exec_globals, exec_locals)
    exec_globals[function_name] = exec_locals[function_name]

    # Return a function that imports necessary modules and calls the target function
    def wrapped_function(*args, **kwargs):
        for module_name, module in exec_globals.items():
            if isinstance(module, type(importlib)):
                globals()[module_name] = module

        return exec_globals[function_name](*args, **kwargs)

    return wrapped_function


def create_class(code, class_name):
    """Dynamically create a class from a string of code and a specified class name.

    Args:
        code: String containing the Python code defining the class
        class_name: Name of the class to be created

    Returns:
         A function that, when called, returns an instance of the created class

    Raises:
        ValueError: If the code contains syntax errors or the class definition is invalid
    """
    if not hasattr(ast, "TypeIgnore"):
        ast.TypeIgnore = create_type_ignore_class()

    code = code.replace("from langflow import CustomComponent", "from langflow.custom import CustomComponent")
    code = code.replace(
        "from langflow.interface.custom.custom_component import CustomComponent",
        "from langflow.custom import CustomComponent",
    )

    try:
        module = ast.parse(code)
        exec_globals = prepare_global_scope(module)
        # Static check for symbols referenced inside method bodies that the
        # exec above won't catch (Python only resolves Name nodes at call
        # time, so a missing import that's only referenced inside
        # ``def build(self):`` would otherwise pass validation and crash at
        # runtime with no hint).
        _check_function_body_name_resolution(module, exec_globals)
        # ``prepare_global_scope`` already exec'd the class definition into
        # ``exec_globals``. Mirror imported modules into our own globals so
        # subsequent executions share them (preserved from the prior
        # ``build_class_constructor`` side-effect).
        # TODO: scope this to a contained mapping. Right now every dynamically
        # created component permanently injects its imported modules into
        # ``lfx.custom.validate``'s module globals; over a long-running server
        # with many user components this can grow unbounded and shadow names.
        for name, value in exec_globals.items():
            if isinstance(value, type(importlib)):
                globals()[name] = value
        return exec_globals[class_name]

    except SyntaxError as e:
        msg = f"Syntax error in code: {e!s}"
        raise ValueError(msg) from e
    except NameError as e:
        missing = getattr(e, "name", None)
        # Cover both cases: the user forgot the import line entirely, AND the
        # case where they have the line but the underlying package is broken
        # (proxy resolution side-effects can surface as a NameError on a later
        # access even when the import statement parsed). The hint avoids
        # blaming the user for a missing line they already have.
        msg = _format_undefined_name_message(missing, str(e))
        raise ValueError(msg) from e
    except ValidationError as e:
        messages = [error["msg"].split(",", 1) for error in e.errors()]
        error_message = "\n".join([message[1] if len(message) > 1 else message[0] for message in messages])
        raise ValueError(error_message) from e
    except (ImportError, ModuleNotFoundError) as e:
        # Surface lazy-proxy resolution failures (and any other import-time
        # error raised during class-body exec, decorators, or class-level
        # instantiations) distinctly from the generic catch-all below. Without
        # this branch the user sees "Error creating class. ImportError(...)"
        # with no signal that the fix is a package install / environment
        # repair rather than a code typo.
        missing_module = getattr(e, "name", None)
        install_hint = (
            f" Ensure the '{missing_module}' package is installed and importable in this environment."
            if missing_module
            else ""
        )
        msg = f"Import error while creating class: {e!s}.{install_hint}"
        raise ValueError(msg) from e
    except AttributeError as e:
        # Sibling case to the ImportError branch above, scoped narrowly to the
        # circular-import / partial-init signature we know about (torch 2.x
        # nested under langchain via transformers). The lazy-import refactor
        # delays `importlib.import_module(...)` to first attribute access on
        # a `_LazyImportProxy`, so a broken transitive import surfaces here
        # as AttributeError rather than ImportError; without this branch the
        # generic catch-all would wrap it as "Error creating class.
        # AttributeError(...)" which reads like a code typo even though the
        # fix is environment-level.
        #
        # Other AttributeErrors (legitimate user bugs like ``self.foo.bar``
        # where ``foo`` is None) are wrapped with the same shape as the
        # generic-Exception handler below ("Error creating class. AttributeError(...)")
        # so the user sees the actual exception type and is not mis-directed
        # toward a torch/transformers environment fix. Inlining instead of
        # ``raise`` because Python does not re-enter the except chain.
        msg_text = str(e)
        if "partially initialized module" in msg_text or "circular import" in msg_text:
            hint = (
                " This usually means a transitive C-extension import (commonly torch via transformers/"
                "langchain) failed to fully initialize. Reinstalling the broken package, pinning a known-"
                "good version, or restarting the interpreter typically resolves it."
            )
            msg = f"Attribute error while creating class: {msg_text}.{hint}"
        else:
            msg = f"Error creating class. {type(e).__name__}({msg_text})."
        raise ValueError(msg) from e
    except ValueError:
        # Static analysis (_check_function_body_name_resolution) and any other
        # branch above that already raises a fully-formatted ValueError. Pass
        # through unchanged so the actionable hint reaches the caller without
        # being wrapped as "Error creating class. ValueError(...)".
        raise
    except Exception as e:
        msg = f"Error creating class. {type(e).__name__}({e!s})."
        raise ValueError(msg) from e


def create_type_ignore_class():
    """Create a TypeIgnore class for AST module if it doesn't exist.

    Returns:
        TypeIgnore class
    """

    class TypeIgnore(ast.AST):
        _fields = ()

    return TypeIgnore


def _import_module_with_warnings(module_name):
    """Import module with appropriate warning suppression."""
    if "langchain" in module_name:
        from langchain_core._api.deprecation import LangChainDeprecationWarning

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", LangChainDeprecationWarning)
            return importlib.import_module(module_name)
    return importlib.import_module(module_name)


def _resolve_attribute(imported_module, module_name, attr_name):
    """Resolve a single attribute from a module, falling back to langchain_classic if needed."""
    try:
        return getattr(imported_module, attr_name)
    except AttributeError:
        pass

    # Try importing as a submodule
    try:
        return importlib.import_module(f"{module_name}.{attr_name}")
    except ModuleNotFoundError:
        pass

    # For langchain modules, try the langchain_classic equivalent
    if module_name.startswith("langchain."):
        classic_module_name = module_name.replace("langchain.", "langchain_classic.", 1)
        classic_module = importlib.import_module(classic_module_name)
        return getattr(classic_module, attr_name)

    msg = f"Cannot import name '{attr_name}' from '{module_name}'"
    raise ImportError(msg)


def _handle_module_attributes(imported_module, node, module_name, exec_globals):
    """Bind names from `from <module_name> import ...` into `exec_globals`.

    Honors `alias.asname` (`from X import Y as Z` binds Z, not Y) and expands `*` to the
    module's public surface (its `__all__` if defined, otherwise every non-underscore attr).
    """
    for alias in node.names:
        if alias.name == "*":
            public_names = getattr(imported_module, "__all__", None)
            if public_names is None:
                public_names = [name for name in dir(imported_module) if not name.startswith("_")]
            for name in public_names:
                exec_globals[name] = _resolve_attribute(imported_module, module_name, name)
            continue
        binding_name = alias.asname or alias.name
        exec_globals[binding_name] = _resolve_attribute(imported_module, module_name, alias.name)


class _MissingModulePlaceholder:
    """Placeholder for modules unavailable on the current platform (e.g. jq on Windows).

    Allows class creation and update_build_config to succeed. Any attribute
    access raises ModuleNotFoundError so that actual usage at runtime fails
    with a clear error.
    """

    def __init__(self, module_name: str) -> None:
        self._module_name = module_name

    def __getattr__(self, name: str):
        msg = f"No module named '{self._module_name}'"
        raise ModuleNotFoundError(msg)


def _get_module_fallbacks(module_name: str) -> list[str]:
    """Return a list of module names to try, including compatibility fallbacks.

    Handles langflow -> lfx and langchain -> langchain_classic remapping at the
    module level (for entirely removed modules). Attribute-level fallback for
    removed attributes in still-existing modules is handled by _resolve_attribute.

    Both fallbacks only trigger on import failure, so new langchain 1.0 imports
    are never replaced.
    """
    names = [module_name]
    if module_name.startswith("langflow."):
        names.append(module_name.replace("langflow.", "lfx.", 1))
    if module_name.startswith("langchain."):
        names.append(module_name.replace("langchain.", "langchain_classic.", 1))
    return names


# Sentinel for the resolution cache; distinguishes "not yet resolved" from a legitimately
# resolved `None` (e.g. `from some_module import some_optional_constant` where the value is None).
_UNSET: object = object()


class _LazyImportProxy:
    """Stand-in object placed in exec_globals that resolves its underlying import on first use.

    CPython bypasses `__missing__` / `__getitem__` on dict subclasses for name lookups at
    class-body scope (see CPython #33128), so the lazy mechanism cannot live on the globals
    dict itself. Instead each deferred name is bound to a proxy instance that triggers the
    real importlib.import_module() the first time something actually touches it through one
    of the explicitly-forwarded dunders (attribute access, call, subclass-base, isinstance
    rhs, iteration). Untouched dunders (truthiness, len, hash, equality, ...) remain on the
    proxy itself; the proxy is intentionally not a transparent wrapper.

    Two shapes are supported:
      - `attr_name=None`: `import X` / `import X as Y` -- the proxy resolves to the bound
        module object (top-level package for plain `import X.Y.Z`, the leaf otherwise).
      - `attr_name=str`: `from X import Y` / `from X import Y as Z` -- resolves to
        `getattr(importlib.import_module(module_name), attr_name)` with the same
        `_resolve_attribute` / `_get_module_fallbacks` semantics as the eager path.
    """

    __slots__ = ("_attr_name", "_is_module_binding", "_module_name", "_resolved", "_top_level")

    def __init__(self, module_name: str, attr_name: str | None, *, is_module_binding: bool, top_level: bool) -> None:
        # `object.__setattr__` bypasses our own `__getattr__` machinery, which delegates to
        # `_resolve()` and would crash before construction completes.
        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_attr_name", attr_name)
        object.__setattr__(self, "_is_module_binding", is_module_binding)
        object.__setattr__(self, "_top_level", top_level)
        object.__setattr__(self, "_resolved", _UNSET)

    def _resolve(self):
        resolved = object.__getattribute__(self, "_resolved")
        if resolved is not _UNSET:
            return resolved

        module_name = object.__getattribute__(self, "_module_name")
        attr_name = object.__getattribute__(self, "_attr_name")
        is_module_binding = object.__getattribute__(self, "_is_module_binding")
        top_level = object.__getattribute__(self, "_top_level")

        # torch 2.x has a fragile partial-init order: when it is first imported
        # *nested* inside another module's __init__ chain (e.g. transformers
        # under langchain_classic.agents), Python publishes a half-initialized
        # `sys.modules["torch"]` whose ``torch.library`` attribute does not yet
        # exist, surfacing as "partially initialized module 'torch' has no
        # attribute 'library' (most likely due to a circular import)". This
        # never happened on the pre-cold-start branch because the eager top-level
        # imports in lfx.custom.validate forced torch to fully initialize once
        # at lfx import time. Pre-load torch here when the lazy proxy is about
        # to walk a transitive chain that almost always pulls it (langchain
        # families known to depend on transformers/torch). Cheap when torch is
        # already loaded, no-op when torch is not installed.
        #
        # Scope: first-segment match, so bare ``langchain`` (the umbrella
        # package, which re-exports langchain_classic.agents et al) is also
        # covered. Direct user imports of transformers / torch from outside
        # the langchain family are NOT pre-primed here; they go through the
        # standard import path and inherit whatever partial-init risk Python
        # gives them.
        top_segment = module_name.split(".", 1)[0]
        if top_segment in {"langchain", "langchain_classic", "langchain_community"}:
            with contextlib.suppress(ImportError):
                importlib.import_module("torch")
                logger.debug("Pre-primed torch for langchain-family proxy: %s", module_name)

        try:
            if is_module_binding:
                # "import X" / "import X as Y" / "import X.Y.Z"
                last_error: ModuleNotFoundError | None = None
                module_obj = None
                for candidate in _get_module_fallbacks(module_name):
                    try:
                        module_obj = importlib.import_module(candidate)
                        break
                    except ModuleNotFoundError as exc:
                        last_error = exc
                        continue

                if module_obj is None:
                    if sys.platform == "win32":
                        placeholder = _MissingModulePlaceholder(module_name)
                        object.__setattr__(self, "_resolved", placeholder)
                        logger.debug("Module '%s' unavailable on Windows; inserted placeholder", module_name)
                        return placeholder
                    # Non-Windows: surface the real error from the last candidate so the
                    # traceback names the package that actually failed (not just the canonical name).
                    if last_error is not None:
                        raise last_error
                    msg = f"Module {module_name} not found. Please install it and try again"
                    raise ModuleNotFoundError(msg)

                if top_level:
                    top = module_name.split(".")[0]
                    resolved = sys.modules.get(top, module_obj)
                else:
                    resolved = module_obj
            else:
                # "from X import Y" -- reuse the eager-path helpers so fallbacks stay identical.
                last_error = None
                imported_module = None
                resolved_module_name = module_name
                for candidate in _get_module_fallbacks(module_name):
                    try:
                        imported_module = _import_module_with_warnings(candidate)
                        resolved_module_name = candidate
                        break
                    except ModuleNotFoundError as exc:
                        last_error = exc
                        continue

                if imported_module is None:
                    if last_error is not None:
                        raise last_error
                    msg = f"Module {module_name} not found. Please install it and try again"
                    raise ModuleNotFoundError(msg)

                resolved = _resolve_attribute(imported_module, resolved_module_name, attr_name)
        except (ImportError, AttributeError):
            # Deferred imports surface their failure at first use, not at parse time. The
            # exception itself is correct, but the traceback points at the user's usage
            # site (e.g. `agent.from_agent_and_tools(...)`) rather than at the originating
            # `from X import Y` line. Log the target name so debugging has a starting point;
            # let the exception propagate unchanged. Logging itself must never replace the
            # real exception, so any failure inside the logger is swallowed.
            target = f"{module_name}.{attr_name}" if attr_name else module_name
            log_exception = getattr(logger, "exception", None)
            if callable(log_exception):
                # Diagnostic logging only — must never replace the real import failure.
                with contextlib.suppress(Exception):
                    log_exception("Deferred import of '%s' failed at first use", target)
            raise

        object.__setattr__(self, "_resolved", resolved)
        return resolved

    # The dunders below must be defined explicitly because Python looks up special methods
    # on the *type*, not via `__getattr__` on the instance — so a missing `__call__` on the
    # class would not delegate to the resolved object even if `_resolve()` returned a callable.
    # Each entry forwards an access pattern actually exercised by component code.

    def __mro_entries__(self, bases):
        # Invoked when the proxy appears in a class's `bases` tuple, so `class Foo(LazyName):`
        # resolves the proxy at class-creation time and the generated class inherits from the
        # real target rather than from the proxy.
        return (self._resolve(),)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)

    def __instancecheck__(self, instance):
        # Only fires when the proxy is the *right-hand side* of `isinstance(x, proxy)`.
        # `isinstance(proxy_instance, RealClass)` does NOT trigger this — it inspects
        # `type(proxy_instance)`, which is `_LazyImportProxy`.
        return isinstance(instance, self._resolve())

    def __subclasscheck__(self, subclass):
        # Symmetric to __instancecheck__: only fires when the proxy is the rhs of
        # `issubclass(cls, proxy)`.
        return issubclass(subclass, self._resolve())

    def __iter__(self):
        return iter(self._resolve())

    def __getitem__(self, item):
        return self._resolve()[item]

    def __or__(self, other):
        return self._resolve() | other

    def __ror__(self, other):
        return other | self._resolve()

    def __repr__(self) -> str:
        # Intentionally does NOT resolve — useful for logging while debugging the lazy path
        # without forcing every `repr()` to import the underlying module.
        module_name = object.__getattribute__(self, "_module_name")
        attr_name = object.__getattribute__(self, "_attr_name")
        target = f"{module_name}.{attr_name}" if attr_name else module_name
        return f"<_LazyImportProxy {target}>"


class _LazyExecGlobals(dict):
    """Globals mapping for `prepare_global_scope` that holds deferred imports as `_LazyImportProxy` values.

    Nominal subclass of `dict` (no behavioral overrides on lookup) because CPython bypasses
    `__missing__` / `__getitem__` on dict subclasses for name lookups at class-body scope
    (CPython #33128). The laziness therefore lives in the *values* (proxies bound by
    `prepare_global_scope` for each deferred `import` / `from X import Y` node), not the
    container. `importlib.import_module(...)` only fires on first real use of a proxy
    (attribute access, call, class base, isinstance rhs, iteration). Components that never
    reference `AgentExecutor` never import `langchain_classic.agents`, so transformers and
    torch never load on paths that do not need them.

    The class also serves as a marker type for tests that want to assert
    `prepare_global_scope` returned a lazy mapping rather than a plain dict.

    Star imports (`from X import *`) are still resolved eagerly because they depend on the
    full module namespace, matching the pre-existing semantics.
    """

    def __init__(self, base: dict | None = None) -> None:
        super().__init__(base or {})

    def copy(self) -> "_LazyExecGlobals":
        # `dict.copy()` returns a plain `dict`, which would silently strip the marker type.
        # Preserve it so callers that copy `exec_globals` (e.g. for nested exec scopes) keep
        # the laziness contract intact.
        return _LazyExecGlobals(self)


# Module prefixes whose imports we defer. These are the heavy langchain entrypoints that
# (transitively) pull transformers + torch. Names bound from these modules are only used
# as types/callables in component code, never as constants passed to Pydantic validators,
# so the proxy stand-in is safe. All other modules (lfx.*, pydantic, stdlib, ...) resolve
# eagerly to preserve existing behavior for string constants and other non-proxyable uses.
_LAZY_MODULE_PREFIXES: tuple[str, ...] = (
    "langchain",
    "langchain_core",
    "langchain_classic",
    "langchain_text_splitters",
    "langchain_community",
)


def _should_defer_module(module_name: str) -> bool:
    """Return True if imports from `module_name` should go through `_LazyImportProxy`.

    Only langchain-family modules are deferred. Lazy proxies are incompatible with strict
    Pydantic type validation on string / enum constants, and non-langchain imports from
    `DEFAULT_IMPORT_STRING` (lfx.io, lfx.schema.*) are cheap to load eagerly.
    """
    top = module_name.split(".", 1)[0]
    return top in _LAZY_MODULE_PREFIXES


def _eager_import(node: ast.Import, exec_globals: dict) -> None:
    """Eager fallback for `import X` / `import X.Y.Z` / `import X as Y` nodes."""
    for alias in node.names:
        module_name = alias.name

        module_obj = None
        for candidate in _get_module_fallbacks(module_name):
            try:
                module_obj = importlib.import_module(candidate)
                break
            except ModuleNotFoundError:
                continue

        if module_obj is None:
            if sys.platform == "win32":
                variable_name = alias.asname or module_name.split(".")[0]
                exec_globals[variable_name] = _MissingModulePlaceholder(module_name)
                logger.debug("Module '%s' unavailable on Windows; inserted placeholder", module_name)
                continue
            module_obj = importlib.import_module(module_name)

        if alias.asname:
            exec_globals[alias.asname] = module_obj
        else:
            variable_name = module_name.split(".")[0]
            exec_globals[variable_name] = sys.modules.get(variable_name, module_obj)


def _eager_import_from(node: ast.ImportFrom, exec_globals: dict) -> None:
    """Eager fallback for `from X import Y` nodes."""
    module_names_to_try = _get_module_fallbacks(node.module)

    last_error: ModuleNotFoundError | None = None
    for candidate in module_names_to_try:
        try:
            imported_module = _import_module_with_warnings(candidate)
            _handle_module_attributes(imported_module, node, candidate, exec_globals)
        except ModuleNotFoundError as exc:
            last_error = exc
            continue
        else:
            return

    if last_error is not None:
        raise last_error
    msg = f"Module {node.module} not found. Please install it and try again"
    raise ModuleNotFoundError(msg)


def prepare_global_scope(module):
    """Prepares the global scope for the provided code module with lazy langchain imports.

    Walks `module.body` once for `Import` / `ImportFrom` nodes (binding either a
    `_LazyImportProxy` or a real object into `exec_globals` per alias), then executes class /
    function / assignment definitions against that scope. For imports whose module is in
    `_LAZY_MODULE_PREFIXES` (langchain family), the proxy defers
    `importlib.import_module(...)` to first real use. For all other imports, resolution is
    eager to preserve backward-compat with strict Pydantic validators and other call sites
    that expect real objects (e.g. string constants from `lfx.utils.constants`).

    Star imports (`from X import *`) always resolve eagerly because they require the full
    module namespace. The Windows `_MissingModulePlaceholder` path is preserved for both
    eager and lazy branches.

    Args:
        module: AST parsed module.

    Returns:
        `_LazyExecGlobals` mapping suitable for passing to `exec(compiled_code, exec_globals)`.

    Raises:
        ModuleNotFoundError: If an eagerly-resolved module is missing. Lazy imports surface
            their error at first use of the proxy instead.
    """
    # Seed the exec namespace with this module's globals so helpers referenced from
    # `DEFAULT_IMPORT_STRING` (e.g. typing aliases) are visible to the compiled class body.
    exec_globals = _LazyExecGlobals(globals())
    future_imports = []

    for node in module.body:
        # ``from __future__ import …`` directives must remain in the AST passed to
        # compile() — they are compile-time pragmas (e.g. PEP 563 ``annotations``),
        # not runtime imports. Components relying on lazy annotation evaluation
        # (``-> list[Tool]`` with ``Tool`` only under TYPE_CHECKING) would NameError
        # at class-body time without this.
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            future_imports.append(node)
            continue
        if isinstance(node, ast.Import):
            # Each alias on a single `import` node decides independently whether to defer.
            lazy_aliases = [a for a in node.names if _should_defer_module(a.name)]
            eager_aliases = [a for a in node.names if not _should_defer_module(a.name)]

            for alias in lazy_aliases:
                module_name = alias.name
                if alias.asname:
                    exec_globals[alias.asname] = _LazyImportProxy(
                        module_name,
                        None,
                        is_module_binding=True,
                        top_level=False,
                    )
                else:
                    variable_name = module_name.split(".")[0]
                    exec_globals[variable_name] = _LazyImportProxy(
                        module_name,
                        None,
                        is_module_binding=True,
                        top_level=True,
                    )

            if eager_aliases:
                _eager_import(ast.Import(names=eager_aliases), exec_globals)

        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            # Star imports bypass the lazy map entirely; they always resolve eagerly.
            if any(alias.name == "*" for alias in node.names):
                _eager_import_from(node, exec_globals)
                continue

            if _should_defer_module(node.module):
                for alias in node.names:
                    binding_name = alias.asname or alias.name
                    exec_globals[binding_name] = _LazyImportProxy(
                        node.module,
                        alias.name,
                        is_module_binding=False,
                        top_level=False,
                    )
            else:
                _eager_import_from(node, exec_globals)

    # Class / function / assignment definitions still execute now. Non-langchain name
    # references resolve eagerly against the already-populated exec_globals; langchain
    # references resolve through `_LazyImportProxy` on first real use.
    definitions = [
        node for node in module.body if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.Assign | ast.AnnAssign)
    ]

    # Ensure `from __future__ import annotations` (PEP 563) is always active so that
    # type annotations in class bodies are stored as strings rather than evaluated eagerly.
    # Without this, `SomeProxiedType | None` in a field annotation would call `__or__` on
    # the `_LazyImportProxy` at class-construction time and raise TypeError.
    has_future_annotations = any(any(alias.name == "annotations" for alias in node.names) for node in future_imports)
    if not has_future_annotations:
        future_imports.insert(
            0,
            ast.fix_missing_locations(
                ast.ImportFrom(
                    module="__future__",
                    names=[ast.alias(name="annotations")],
                    level=0,
                )
            ),
        )

    if definitions or future_imports:
        combined_module = ast.Module(body=future_imports + definitions, type_ignores=[])
        compiled_code = compile(combined_module, "<string>", "exec")
        exec(compiled_code, exec_globals)

    return exec_globals


# Kept for external callers (re-exported via ``from lfx.custom.validate import *``
# in langflow.utils.validate / langflow.custom.validate). ``create_class`` no
# longer goes through these — ``prepare_global_scope`` already exec's the
# class into ``exec_globals``, so the chain below is redundant work.
def extract_class_code(module, class_name):
    """Extracts the AST node for the specified class from the module.

    Args:
        module: AST parsed module
        class_name: Name of the class to extract

    Returns:
        AST node of the specified class
    """
    class_code = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == class_name)

    class_code.parent = None
    return class_code


def compile_class_code(class_code):
    """Compiles the AST node of a class into a code object.

    Args:
        class_code: AST node of the class

    Returns:
        Compiled code object of the class
    """
    return compile(ast.Module(body=[class_code], type_ignores=[]), "<string>", "exec")


def build_class_constructor(compiled_class, exec_globals, class_name):
    """Builds a constructor function for the dynamically created class.

    Args:
        compiled_class: Compiled code object of the class
        exec_globals: Global scope with necessary imports
        class_name: Name of the class

    Returns:
         Constructor function for the class
    """
    exec_locals = dict(locals())
    exec(compiled_class, exec_globals, exec_locals)
    exec_globals[class_name] = exec_locals[class_name]

    # Return a function that imports necessary modules and creates an instance of the target class
    def build_custom_class():
        for module_name, module in exec_globals.items():
            if isinstance(module, type(importlib)):
                globals()[module_name] = module

        return exec_globals[class_name]

    return build_custom_class()


def extract_function_name(code):
    module = ast.parse(code)
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            return node.name
    msg = "No function definition found in the code string"
    raise ValueError(msg)


def extract_class_name(code: str) -> str:
    """Extract the name of the first Component subclass found in the code.

    Args:
        code (str): The source code to parse

    Returns:
        str: Name of the first Component subclass found

    Raises:
        TypeError: If no Component subclass is found in the code
    """
    try:
        module = ast.parse(code)
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue

            # Check bases for Component inheritance
            # TODO: Build a more robust check for Component inheritance
            for base in node.bases:
                if isinstance(base, ast.Name) and any(pattern in base.id for pattern in ["Component", "LC"]):
                    return node.name

        msg = f"No Component subclass found in the code string. Code snippet: {code[:100]}"
        raise TypeError(msg)
    except SyntaxError as e:
        msg = f"Invalid Python code: {e!s}"
        raise ValueError(msg) from e
