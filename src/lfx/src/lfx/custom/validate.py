import ast
import contextlib
import copy
import importlib
import sys
import warnings
from types import FunctionType, ModuleType
from typing import Optional, Union

from langchain_core._api.deprecation import LangChainDeprecationWarning
from pydantic import ValidationError

from lfx.custom.annotation_validation import (
    UnsafeReturnAnnotationError,
    register_compiled_class_method_returns,
    snapshot_trusted_class_method_returns,
    validate_return_annotations,
)
from lfx.field_typing.constants import CUSTOM_COMPONENT_SUPPORTED_TYPES, DEFAULT_IMPORT_STRING
from lfx.log.logger import logger

_LANGFLOW_IS_INSTALLED = False
_VECTOR_STORE_CONNECTION_MODULE = "lfx.base.vectorstores.vector_store_connection_decorator"

with contextlib.suppress(ImportError):
    import langflow  # noqa: F401

    _LANGFLOW_IS_INSTALLED = True


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

    # Validate each function definition WITHOUT executing it.
    #
    # Security (GHSA-2wcq-pvw2-xh7v): this endpoint only
    # *validates* code, but it previously compiled and exec()'d every function
    # definition. Executing a function definition evaluates its decorators and
    # default-argument expressions at definition time, so a payload such as
    #     def f(x=__import__("os").system("...")): ...
    # achieves arbitrary code execution during "validation" — the function never
    # has to be called. Compile only, to surface syntax/compile errors; never
    # exec untrusted code on the validation path.
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            try:
                compile(ast.Module(body=[node], type_ignores=[]), "<string>", "exec")
            except Exception as e:  # noqa: BLE001
                logger.debug("Error compiling function code", exc_info=True)
                errors["function"]["errors"].append(str(e))

    # Return the errors dictionary
    return errors


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


def _trusted_vector_store_decorator_alias(module: ast.Module, class_name: str) -> str | None:
    """Recognize an unshadowed canonical vector-store decorator import."""
    class_node = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    if len(class_node.decorator_list) != 1 or not isinstance(class_node.decorator_list[0], ast.Name):
        return None

    decorator_name = class_node.decorator_list[0].id
    approved_import = None
    for node in module.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != _VECTOR_STORE_CONNECTION_MODULE:
            continue
        for imported in node.names:
            if imported.name == "vector_store_connection" and (imported.asname or imported.name) == decorator_name:
                if approved_import is not None:
                    msg = f"Trusted vector-store decorator alias '{decorator_name}' is bound more than once."
                    raise UnsafeReturnAnnotationError(msg)
                approved_import = imported
    if approved_import is None:
        return None

    for node in ast.walk(module):
        if node is approved_import:
            continue
        if isinstance(node, ast.Name) and node.id == decorator_name and isinstance(node.ctx, ast.Store | ast.Del):
            break
        if isinstance(node, ast.arg) and node.arg == decorator_name:
            break
        if isinstance(node, ast.alias):
            bound_name = node.asname or node.name.split(".", 1)[0]
            if node.name == "*" or bound_name == decorator_name:
                break
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and node.name == decorator_name:
            break
        if isinstance(node, ast.ExceptHandler) and node.name == decorator_name:
            break
        if isinstance(node, ast.MatchAs | ast.MatchStar) and node.name == decorator_name:
            break
        if isinstance(node, ast.MatchMapping) and node.rest == decorator_name:
            break
    else:
        return decorator_name

    msg = f"Trusted vector-store decorator alias '{decorator_name}' is shadowed or rebound."
    raise UnsafeReturnAnnotationError(msg)


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
    from langchain_core.vectorstores import VectorStore

    from lfx.io import Output

    vector_store_type = VectorStore
    output_type = Output
    compiled_return_registrar = register_compiled_class_method_returns

    def apply_vector_store_connection(component_class: type) -> type:
        """Apply trusted behavior without component-controlled global lookups."""
        component_class.decorated = True
        if hasattr(component_class, "outputs"):
            component_class.outputs = component_class.outputs.copy()
            if "vectorstoreconnection" not in [output.name for output in component_class.outputs]:
                component_class.outputs.append(
                    output_type(
                        display_name="Vector Store Connection",
                        hidden=False,
                        name="vectorstoreconnection",
                        method="as_vector_store",
                        group_outputs=False,
                    )
                )

        def as_vector_store(self) -> vector_store_type:
            return self.build_vector_store()

        component_class.as_vector_store = as_vector_store
        return component_class

    if not hasattr(ast, "TypeIgnore"):
        ast.TypeIgnore = create_type_ignore_class()

    code = code.replace("from langflow import CustomComponent", "from langflow.custom import CustomComponent")
    code = code.replace(
        "from langflow.interface.custom.custom_component import CustomComponent",
        "from langflow.custom import CustomComponent",
    )

    code = DEFAULT_IMPORT_STRING + "\n" + code
    try:
        module = ast.parse(code)
        # Return annotations are evaluated by Python during class creation and
        # later by typing.get_type_hints. Reject active syntax before imports,
        # compilation, or component construction can execute it.
        validate_return_annotations(module)
        if not any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in module.body
        ):
            module.body.insert(
                0,
                ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            )
            ast.fix_missing_locations(module)
        trusted_vector_store_alias = _trusted_vector_store_decorator_alias(module, class_name)
        runtime_module = copy.deepcopy(module) if trusted_vector_store_alias is not None else module
        if trusted_vector_store_alias is not None:
            runtime_class_code = extract_class_code(runtime_module, class_name)
            runtime_class_code.decorator_list = []
        trusted_method_returns = {}
        source_class_bindings = {}
        exec_globals = prepare_global_scope(
            runtime_module,
            trusted_method_returns=trusted_method_returns,
            source_class_bindings=source_class_bindings,
        )

        future_imports = [n for n in runtime_module.body if isinstance(n, ast.ImportFrom) and n.module == "__future__"]
        class_code = extract_class_code(module, class_name)
        runtime_class_code = extract_class_code(runtime_module, class_name)
        compiled_class = compile_class_code(runtime_class_code, future_imports)
        preexisting_class_ids = frozenset(id(value) for value in exec_globals.values() if issubclass(type(value), type))
        component_class = build_class_constructor(compiled_class, exec_globals, class_name)
        if trusted_vector_store_alias is not None:
            component_class = apply_vector_store_connection(component_class)
            exec_globals[class_name] = component_class
        try:
            component_mro = type.__getattribute__(component_class, "__mro__")
        except (AttributeError, TypeError):
            component_mro = ()
        for source_node in (node for node in runtime_module.body if isinstance(node, ast.ClassDef)):
            source_base = source_class_bindings.get(id(source_node))
            if source_base is None or not any(source_base is base for base in component_mro[1:]):
                continue
            if source_node.decorator_list or type(source_base) is not type:
                continue
            compiled_return_registrar(
                source_base,
                source_node,
                globalns=exec_globals,
                preexisting_class_ids=preexisting_class_ids,
                trusted_method_returns=trusted_method_returns,
                allow_preexisting_class=True,
                infer_decorated_methods=False,
            )
        compiled_return_registrar(
            component_class,
            class_code,
            globalns=exec_globals,
            preexisting_class_ids=preexisting_class_ids,
            trusted_method_returns=trusted_method_returns,
            trusted_vector_store_applied=trusted_vector_store_alias is not None,
            trusted_vector_store_output=vector_store_type,
        )

    except SyntaxError as e:
        msg = f"Syntax error in code: {e!s}"
        raise ValueError(msg) from e
    except NameError as e:
        msg = f"Name error (possibly undefined variable): {e!s}"
        raise ValueError(msg) from e
    except ValidationError as e:
        messages = [error["msg"].split(",", 1) for error in e.errors()]
        error_message = "\n".join([message[1] if len(message) > 1 else message[0] for message in messages])
        raise ValueError(error_message) from e
    except UnsafeReturnAnnotationError as e:
        raise ValueError(str(e)) from e
    except Exception as e:
        msg = f"Error creating class. {type(e).__name__}({e!s})."
        raise ValueError(msg) from e
    else:
        return component_class


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
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", LangChainDeprecationWarning)
            return importlib.import_module(module_name)
    else:
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
    """Handle importing specific attributes from a module."""
    for alias in node.names:
        key = alias.asname or alias.name
        exec_globals[key] = _resolve_attribute(imported_module, module_name, alias.name)


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


def _static_imported_base(node: ast.AST, exec_globals: dict) -> type | None:
    if isinstance(node, ast.Name):
        value = dict.get(exec_globals, node.id)
    elif isinstance(node, ast.Attribute):
        attributes: list[str] = []
        while isinstance(node, ast.Attribute):
            attributes.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        value = dict.get(exec_globals, node.id)
        for attribute in reversed(attributes):
            if not isinstance(value, ModuleType):
                return None
            namespace = ModuleType.__getattribute__(value, "__dict__")
            if type(namespace) is not dict:
                return None
            value = dict.get(namespace, attribute)
    else:
        return None
    return value if issubclass(type(value), type) else None


def _trusted_imported_bases(module: ast.Module, exec_globals: dict) -> list[type]:
    bases: dict[int, type] = {}
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for base_node in node.bases:
            base = _static_imported_base(base_node, exec_globals)
            if base is not None:
                bases[id(base)] = base
    return list(bases.values())


def _has_static_type_metaclass_bases(class_node: ast.ClassDef, exec_globals: dict) -> bool:
    """Return whether a source class must be freshly created by the built-in type metaclass."""
    if class_node.decorator_list or class_node.keywords:
        return False
    return all(
        (base := _static_imported_base(base_node, exec_globals)) is not None and type(base) is type
        for base_node in class_node.bases
    )


def prepare_global_scope(module, *, trusted_method_returns=None, source_class_bindings=None):
    """Prepares the global scope with necessary imports from the provided code module.

    Args:
        module: AST parsed module
        trusted_method_returns: Optional destination for server-owned method snapshots
        source_class_bindings: Optional destination for exact classes produced by source ClassDefs

    Returns:
        Dictionary representing the global scope with imported modules

    Raises:
        ModuleNotFoundError: If a module is not found in the code
    """
    exec_globals = globals().copy()
    imports = []
    import_froms = []
    future_imports = []
    definitions = []

    for node in module.body:
        if isinstance(node, ast.Import):
            imports.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module == "__future__":
            # __future__ imports are compiler directives — collect separately
            future_imports.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            import_froms.append(node)
        elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef | ast.Assign | ast.AnnAssign):
            definitions.append(node)

    for node in imports:
        for alias in node.names:
            module_name = alias.name

            module_obj = None
            for name in _get_module_fallbacks(module_name):
                try:
                    module_obj = importlib.import_module(name)
                    break
                except ModuleNotFoundError:
                    continue

            if module_obj is None:
                if sys.platform == "win32":
                    # Some C-extension packages (e.g. jq) have no Windows
                    # wheels.  Insert a lazy placeholder so that class creation
                    # succeeds and update_build_config can run.  Any real usage
                    # of the module at runtime will raise ModuleNotFoundError.
                    variable_name = alias.asname or module_name.split(".")[0]
                    exec_globals[variable_name] = _MissingModulePlaceholder(module_name)
                    logger.debug("Module '%s' unavailable on Windows — inserted placeholder", module_name)
                    continue
                # On other platforms the package should be installable, so
                # raise to surface the real error.
                module_obj = importlib.import_module(module_name)

            # Determine the variable name
            if alias.asname:
                # For aliased imports like "import yfinance as yf", use the imported module directly
                variable_name = alias.asname
                exec_globals[variable_name] = module_obj
            else:
                # For dotted imports like "urllib.request", set the variable to the top-level package.
                # importlib.import_module returns the *leaf* module, but Python's import statement
                # binds the top-level package name. Retrieve it from sys.modules instead.
                variable_name = module_name.split(".")[0]
                exec_globals[variable_name] = sys.modules.get(variable_name, module_obj)

    for node in import_froms:
        module_names_to_try = _get_module_fallbacks(node.module)

        success = False
        last_error = None

        for module_name in module_names_to_try:
            try:
                imported_module = _import_module_with_warnings(module_name)
                _handle_module_attributes(imported_module, node, module_name, exec_globals)

                success = True
                break

            except ModuleNotFoundError as e:
                last_error = e
                continue

        if not success:
            # Re-raise the last error to preserve the actual missing module information
            if last_error:
                raise last_error
            msg = f"Module {node.module} not found. Please install it and try again"
            raise ModuleNotFoundError(msg)

    if trusted_method_returns is not None:
        trusted_bases = _trusted_imported_bases(module, exec_globals)
        trusted_method_returns.update(snapshot_trusted_class_method_returns(trusted_bases))

    if definitions:
        # Prepend __future__ imports so compiler directives (e.g. PEP 563 annotations) take effect
        if source_class_bindings is None:
            combined_module = ast.Module(body=future_imports + definitions, type_ignores=[])
            compiled_code = compile(combined_module, "<string>", "exec")
            exec(compiled_code, exec_globals)
        else:
            for definition in definitions:
                safe_source_class = isinstance(definition, ast.ClassDef) and _has_static_type_metaclass_bases(
                    definition, exec_globals
                )
                preexisting_class_ids = {id(value) for value in exec_globals.values() if issubclass(type(value), type)}
                definition_module = ast.Module(body=[*future_imports, definition], type_ignores=[])
                exec(compile(definition_module, "<string>", "exec"), exec_globals)
                if safe_source_class:
                    runtime_class = dict.get(exec_globals, definition.name)
                    if type(runtime_class) is type and id(runtime_class) not in preexisting_class_ids:
                        source_class_bindings[id(definition)] = runtime_class

    return exec_globals


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


def compile_class_code(class_code, future_imports=None):
    """Compiles the AST node of a class into a code object.

    Args:
        class_code: AST node of the class
        future_imports: Optional list of __future__ ImportFrom nodes to prepend as compiler directives

    Returns:
        Compiled code object of the class
    """
    body = (future_imports or []) + [class_code]
    return compile(ast.Module(body=body, type_ignores=[]), "<string>", "exec")


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


# TODO: Remove this function
def get_default_imports(code_string):
    """Returns a dictionary of default imports for the dynamic class constructor."""
    default_imports = {
        "Optional": Optional,
        "List": list,
        "Dict": dict,
        "Union": Union,
    }
    langflow_imports = list(CUSTOM_COMPONENT_SUPPORTED_TYPES.keys())
    necessary_imports = find_names_in_code(code_string, langflow_imports)
    langflow_module = importlib.import_module("lfx.field_typing")
    default_imports.update({name: getattr(langflow_module, name) for name in necessary_imports})

    return default_imports


def find_names_in_code(code, names):
    """Finds if any of the specified names are present in the given code string.

    Args:
        code: The source code as a string.
        names: A list of names to check for in the code.

    Returns:
        A set of names that are found in the code.
    """
    return {name for name in names if name in code}


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
