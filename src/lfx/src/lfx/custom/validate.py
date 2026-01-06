import ast
import contextlib
import importlib
import warnings
from types import FunctionType
from typing import Optional, Union

from langchain_core._api.deprecation import LangChainDeprecationWarning
from pydantic import ValidationError

from lfx.custom.isolation import (
    DunderAccessTransformer,
    SecurityViolationError,
    create_isolated_import,
    execute_in_isolated_env,
)
from lfx.field_typing.constants import CUSTOM_COMPONENT_SUPPORTED_TYPES, DEFAULT_IMPORT_STRING
from lfx.log.logger import logger

_LANGFLOW_IS_INSTALLED = False

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

    # Phase 1: Validate import statements (syntax check only, no code execution)
    # We use isolated_import to check if imports are valid and not blocked by security policy.
    # Note: We don't pass isolated_builtins_dict here because we're only validating imports,
    # not executing code. If someone tries `import builtins`, it will be blocked with an error.
    isolated_import = create_isolated_import()  # None = validation-only mode
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    # Use isolated import - blocks dangerous modules
                    isolated_import(alias.name, None, None, (), 0)
                except SecurityViolationError as e:
                    # SecurityViolationError means the module is blocked by security policy.
                    # Since isolation will be used during runtime execution (planned),
                    # we should fail validation here so users get early feedback about
                    # blocked modules. This prevents code from passing validation but
                    # failing at runtime.
                    errors["imports"]["errors"].append(str(e))
                except ModuleNotFoundError as e:
                    errors["imports"]["errors"].append(str(e))
                except Exception as e:  # noqa: BLE001
                    errors["imports"]["errors"].append(str(e))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                try:
                    # Use isolated import - blocks dangerous modules
                    isolated_import(node.module, None, None, (), 0)
                except SecurityViolationError as e:
                    # SecurityViolationError means the module is blocked by security policy.
                    # Since isolation will be used during runtime execution (planned),
                    # we should fail validation here so users get early feedback about
                    # blocked modules. This prevents code from passing validation but
                    # failing at runtime.
                    errors["imports"]["errors"].append(str(e))
                except ModuleNotFoundError as e:
                    errors["imports"]["errors"].append(str(e))
                except Exception as e:  # noqa: BLE001
                    errors["imports"]["errors"].append(str(e))

    # Phase 2: Transform AST to block dangerous dunder access, then execute function definitions
    # This actually runs the code (for decorators, default args, etc.) in an isolated environment.
    # Unlike Phase 1, this uses execute_in_isolated_env() which creates full isolation including
    # isolated builtins. This is where the real security isolation happens.
    #
    # CRITICAL: Transform AST to block dangerous dunder access before compilation
    # This prevents escapes like: ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
    #
    # SECURITY: Decorators are evaluated at function definition time, which means they execute
    # during validation. By executing function definitions in isolation, decorators are also
    # executed in isolation, blocking RCE attacks via malicious decorators (e.g., @subprocess.run(...)).
    # The transformer visits the entire FunctionDef node, including decorator_list, ensuring
    # decorators are also protected from dunder access attacks.
    transformer = DunderAccessTransformer()

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            # Transform the function node's AST to block dangerous dunder access
            # Visit the entire function node (which will recursively transform all attributes)
            # This includes decorators (decorator_list), which are part of the FunctionDef node
            transformed_func = transformer.visit(node)
            # Fix missing location information
            ast.fix_missing_locations(transformed_func)
            code_obj = compile(ast.Module(body=[transformed_func], type_ignores=[]), "<string>", "exec")
            try:
                # Create execution context with common langflow imports
                exec_globals = _create_langflow_execution_context()
                # Execute in isolated environment - code cannot access server environment
                execute_in_isolated_env(code_obj, exec_globals)
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
                    exec(
                        f"{alias.asname or alias.name} = importlib.import_module('{alias.name}')",
                        exec_globals,
                        locals(),
                    )
                    exec_globals[alias.asname or alias.name] = importlib.import_module(alias.name)
                except ModuleNotFoundError as e:
                    msg = f"Module {alias.name} not found. Please install it and try again."
                    raise ModuleNotFoundError(msg) from e

    function_code = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    function_code.parent = None
    code_obj = compile(ast.Module(body=[function_code], type_ignores=[]), "<string>", "exec")

    try:
        # Use isolated execution environment for security
        # execute_in_isolated_env merges results into exec_globals
        execute_in_isolated_env(code_obj, exec_globals)
        # The function should now be in exec_globals after isolated execution
    except Exception as exc:
        msg = "Function string does not contain a function"
        raise ValueError(msg) from exc

    # Get the function from exec_globals (it was merged by execute_in_isolated_env)
    if function_name not in exec_globals:
        msg = f"Function '{function_name}' was not created during execution"
        raise ValueError(msg)

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
                        exec_globals[alias.asname or alias.name] = importlib.import_module(module_name)
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

    NOTE: Module-level imports are blocked, but runtime imports inside methods are NOT blocked.
    TODO: See RUNTIME_IMPORT_ISOLATION_PLAN.md for plan to block runtime imports in methods.

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

    code = DEFAULT_IMPORT_STRING + "\n" + code
    try:
        module = ast.parse(code)
        exec_globals = prepare_global_scope(module)

        class_code = extract_class_code(module, class_name)
        compiled_class = compile_class_code(class_code)

        return build_class_constructor(compiled_class, exec_globals, class_name)

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
    except SecurityViolationError as e:
        # Include component name in security violation errors for better debugging
        msg = f"Error creating class '{class_name}'. {type(e).__name__}({e!s})."
        raise ValueError(msg) from e
    except Exception as e:
        msg = f"Error creating class '{class_name}'. {type(e).__name__}({e!s})."
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
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", LangChainDeprecationWarning)
            return importlib.import_module(module_name)
    else:
        return importlib.import_module(module_name)


def _handle_module_attributes(imported_module, node, module_name, exec_globals):
    """Handle importing specific attributes from a module."""
    for alias in node.names:
        try:
            # First try getting it as an attribute
            exec_globals[alias.name] = getattr(imported_module, alias.name)
        except AttributeError:
            # If that fails, try importing the full module path
            full_module_path = f"{module_name}.{alias.name}"
            exec_globals[alias.name] = importlib.import_module(full_module_path)


def prepare_global_scope(module):
    """Prepares the global scope with necessary imports from the provided code module.

    Args:
        module: AST parsed module

    Returns:
        Dictionary representing the global scope with imported modules

    Raises:
        ModuleNotFoundError: If a module is not found in the code
        SecurityViolationError: If a blocked module is imported
    """
    exec_globals = globals().copy()
    imports = []
    import_froms = []
    assignments = []  # Module-level assignments (like DEFAULT_OLLAMA_URL)
    definitions = []  # Class and function definitions

    for node in module.body:
        if isinstance(node, ast.Import):
            imports.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            import_froms.append(node)
        elif isinstance(node, ast.Assign):
            # Execute assignments first so they're available for class/function definitions
            assignments.append(node)
        elif isinstance(node, ast.ClassDef | ast.FunctionDef):
            definitions.append(node)

    # Use isolated import function to enforce security restrictions
    # This ensures blocked modules (like subprocess, os, etc.) are caught here
    isolated_import = create_isolated_import()

    for node in imports:
        for alias in node.names:
            module_name = alias.name
            try:
                # Use isolated import to enforce security - will raise SecurityViolationError for blocked modules
                module_obj = isolated_import(module_name, None, None, (), 0)
            except SecurityViolationError:
                # Re-raise security violations
                raise
            except Exception as e:
                # Convert other import errors to ModuleNotFoundError for consistency
                msg = f"Module {module_name} not found. Please install it and try again."
                raise ModuleNotFoundError(msg) from e

            # Determine the variable name
            if alias.asname:
                # For aliased imports like "import yfinance as yf", use the imported module directly
                variable_name = alias.asname
                exec_globals[variable_name] = module_obj
            else:
                # For dotted imports like "urllib.request", set the variable to the top-level package
                variable_name = module_name.split(".")[0]
                # Re-import top-level package using isolated import
                try:
                    exec_globals[variable_name] = isolated_import(variable_name, None, None, (), 0)
                except SecurityViolationError:
                    raise
                except Exception:
                    # If top-level import fails, use the already imported module
                    exec_globals[variable_name] = module_obj

    for node in import_froms:
        module_names_to_try = [node.module]

        # If original module starts with langflow, also try lfx equivalent
        if node.module and node.module.startswith("langflow."):
            lfx_module_name = node.module.replace("langflow.", "lfx.", 1)
            module_names_to_try.append(lfx_module_name)

        success = False
        last_error = None

        for module_name in module_names_to_try:
            try:
                # Use isolated import to enforce security
                imported_module = isolated_import(module_name, None, None, (), 0)
                _handle_module_attributes(imported_module, node, module_name, exec_globals)

                success = True
                break

            except SecurityViolationError:
                # Re-raise security violations
                raise
            except ModuleNotFoundError as e:
                last_error = e
                continue

        if not success:
            # Re-raise the last error to preserve the actual missing module information
            if last_error:
                raise last_error
            msg = f"Module {node.module} not found. Please install it and try again"
            raise ModuleNotFoundError(msg)

    # Execute assignments first so module-level constants are available for class/function definitions
    if assignments:
        assignments_module = ast.Module(body=assignments, type_ignores=[])
        compiled_assignments = compile(assignments_module, "<string>", "exec")
        # Use isolated execution environment for security
        execute_in_isolated_env(compiled_assignments, exec_globals)
        # After execution, assignments are now in exec_globals (merged by execute_in_isolated_env)

    # Now execute class/function definitions, which can reference the assignments above
    if definitions:
        combined_module = ast.Module(body=definitions, type_ignores=[])
        compiled_code = compile(combined_module, "<string>", "exec")
        # Use isolated execution environment for security
        # exec_globals now contains the assignments from above
        execute_in_isolated_env(compiled_code, exec_globals)

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
    # Use isolated execution environment for security
    # execute_in_isolated_env merges results into exec_globals
    execute_in_isolated_env(compiled_class, exec_globals)
    # The class should now be in exec_globals after isolated execution

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
