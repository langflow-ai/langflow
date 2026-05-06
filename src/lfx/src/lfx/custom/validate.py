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
        module = _LEGACY_LFX_IMPORT_HINTS.get(missing) if missing else None
        if module is None and missing:
            # Lazy fallback to langchain symbols so we don't pull names.py at
            # module import. The error path is cold by definition; cost here
            # is irrelevant.
            from lfx.field_typing.names import LANGCHAIN_SYMBOLS

            symbol = LANGCHAIN_SYMBOLS.get(missing)
            if symbol is not None:
                module = symbol[0]
        hint = f" Add `from {module} import {missing}` to your component code." if module else ""
        msg = f"Name error (possibly undefined variable): {e!s}.{hint}"
        raise ValueError(msg) from e
    except ValidationError as e:
        messages = [error["msg"].split(",", 1) for error in e.errors()]
        error_message = "\n".join([message[1] if len(message) > 1 else message[0] for message in messages])
        raise ValueError(error_message) from e
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
