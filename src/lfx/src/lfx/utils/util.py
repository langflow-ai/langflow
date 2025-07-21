"""Utility functions copied from langflow for lfx package."""

import ast
import asyncio
import difflib
import importlib
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from langchain_core._api.deprecation import LangChainDeprecationWarning
from loguru import logger
from pydantic import ValidationError

# Import from lfx modules
from lfx.field_typing.constants import DEFAULT_IMPORT_STRING
from lfx.schema.schema import INPUT_FIELD_NAME


# === Validation utilities ===
def add_type_ignores() -> None:
    if not hasattr(ast, "TypeIgnore"):

        class TypeIgnore(ast.AST):
            _fields = ()

        ast.TypeIgnore = TypeIgnore  # type: ignore[assignment, misc]


def validate_code(code):
    """Validate Python code by parsing and checking imports and function definitions."""
    # Initialize the errors dictionary
    errors = {"imports": {"errors": []}, "function": {"errors": []}}

    # Parse the code string into an abstract syntax tree (AST)
    try:
        tree = ast.parse(code)
    except Exception as e:  # noqa: BLE001
        if hasattr(logger, "opt"):
            logger.opt(exception=True).debug("Error parsing code")
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

    # Evaluate the function definition
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            code_obj = compile(ast.Module(body=[node], type_ignores=[]), "<string>", "exec")
            try:
                exec(code_obj)
            except Exception as e:  # noqa: BLE001
                logger.opt(exception=True).debug("Error executing function code")
                errors["function"]["errors"].append(str(e))

    # Return the errors dictionary
    return errors


def validate(code):
    """Main validation function - wrapper around validate_code."""
    return validate_code(code)


# === Class utilities ===
def get_base_classes(cls):
    """Get the base classes of a class.

    These are used to determine the output of the nodes.
    """
    if hasattr(cls, "__bases__") and cls.__bases__:
        bases = cls.__bases__
        result = []
        for base in bases:
            if any(_type in base.__module__ for _type in ["pydantic", "abc"]):
                continue
            result.append(base.__name__)
            base_classes = get_base_classes(base)
            # check if the base_classes are in the result
            # if not, add them
            for base_class in base_classes:
                if base_class not in result:
                    result.append(base_class)
    else:
        result = [cls.__name__]
    if not result:
        result = [cls.__name__]
    return list({*result, cls.__name__})


# === String utilities ===
def find_closest_match(string: str, list_of_strings: list[str]) -> str | None:
    """Find the closest match in a list of strings."""
    closest_match = difflib.get_close_matches(string, list_of_strings, n=1, cutoff=0.2)
    if closest_match:
        return closest_match[0]
    return None


# === Async utilities ===
if hasattr(asyncio, "timeout"):

    @asynccontextmanager
    async def timeout_context(timeout_seconds):
        with asyncio.timeout(timeout_seconds) as ctx:
            yield ctx
else:

    @asynccontextmanager
    async def timeout_context(timeout_seconds):
        try:
            yield await asyncio.wait_for(asyncio.Future(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            msg = f"Operation timed out after {timeout_seconds} seconds"
            raise TimeoutError(msg) from e


def run_until_complete(coro):
    """Run a coroutine until completion, handling existing event loops."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # If there's no event loop, create a new one and run the coroutine
        return asyncio.run(coro)
    # If there's already a running event loop, we can't call run_until_complete on it
    # Instead, we need to run the coroutine in a new thread with a new event loop

    def run_in_new_loop():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    with ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_new_loop)
        return future.result()


# === Type utilities ===
def format_type(type_: Any) -> str:
    """Format a type for display."""
    if type_ is str:
        type_ = "Text"
    elif hasattr(type_, "__name__"):
        type_ = type_.__name__
    elif hasattr(type_, "__class__"):
        type_ = type_.__class__.__name__
    else:
        type_ = str(type_)
    return type_


# === Flow utilities ===
INPUT_TYPE_MAP = {
    "ChatInput": {"type_hint": "Optional[str]", "default": '""'},
    "TextInput": {"type_hint": "Optional[str]", "default": '""'},
    "JSONInput": {"type_hint": "Optional[dict]", "default": "{}"},
}


async def list_flows(*, user_id: str | None = None):
    """List flows for a user."""
    # TODO: We may need to build a list flows that relies on calling
    # the API or the db like langflow's list_flows does.
    try:
        from langflow.helpers.flow import list_flows as langflow_list_flows

        return await langflow_list_flows(user_id=user_id)
    except ImportError:
        logger.error("Error listing flows: langflow.helpers.flow is not available")
        return []


async def load_flow(user_id: str, flow_id: str | None = None, flow_name: str | None = None, tweaks: dict | None = None):
    """Load a flow graph."""


async def find_flow(flow_name: str, user_id: str) -> str | None:
    """Find a flow by name for a user."""


async def run_flow(
    inputs: dict | list[dict] | None = None,
    tweaks: dict | None = None,
    flow_id: str | None = None,
    flow_name: str | None = None,
    output_type: str | None = "chat",
    user_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    graph=None,
):
    """Run a flow with given inputs."""
    from typing import cast

    if user_id is None:
        msg = "Session is invalid"
        raise ValueError(msg)
    if graph is None:
        graph = await load_flow(user_id, flow_id, flow_name, tweaks)
    if run_id:
        graph.set_run_id(UUID(run_id))
    if session_id:
        graph.session_id = session_id
    if user_id:
        graph.user_id = user_id

    if inputs is None:
        inputs = []
    if isinstance(inputs, dict):
        inputs = [inputs]
    inputs_list = []
    inputs_components = []
    types = []
    for input_dict in inputs:
        inputs_list.append({INPUT_FIELD_NAME: cast("str", input_dict.get("input_value"))})
        inputs_components.append(input_dict.get("components", []))
        types.append(input_dict.get("type", "chat"))

    outputs = [
        vertex.id
        for vertex in graph.vertices
        if output_type == "debug"
        or (
            vertex.is_output and (output_type == "any" or output_type in vertex.id.lower())  # type: ignore[operator]
        )
    ]

    fallback_to_env_vars = True  # get_settings_service().settings.fallback_to_env_var

    return await graph.arun(
        inputs_list,
        outputs=outputs,
        inputs_components=inputs_components,
        types=types,
        fallback_to_env_vars=fallback_to_env_vars,
    )


# === Code creation utilities ===
def create_class(code, class_name):
    """Dynamically create a class from a string of code and a specified class name."""
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
    except Exception as e:
        msg = f"Error creating class: {e!s}"
        raise ValueError(msg) from e


def create_type_ignore_class():
    """Create a TypeIgnore class for AST module if it doesn't exist."""

    class TypeIgnore(ast.AST):
        _fields = ()

    return TypeIgnore


def prepare_global_scope(module):
    """Prepares the global scope with necessary imports from the provided code module."""
    exec_globals = globals().copy()
    imports = []
    import_froms = []
    definitions = []

    for node in module.body:
        if isinstance(node, ast.Import):
            imports.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            import_froms.append(node)
        elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.Assign):
            definitions.append(node)

    for node in imports:
        for alias in node.names:
            try:
                module_name = alias.name
                variable_name = alias.asname or alias.name
                exec_globals[variable_name] = importlib.import_module(module_name)
            except ModuleNotFoundError as e:
                msg = f"Module {alias.name} not found. Please install it and try again."
                raise ModuleNotFoundError(msg) from e

    for node in import_froms:
        try:
            module_name = node.module
            # Apply warning suppression only when needed
            if "langchain" in module_name:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", LangChainDeprecationWarning)
                    imported_module = importlib.import_module(module_name)
            else:
                imported_module = importlib.import_module(module_name)

            for alias in node.names:
                try:
                    # First try getting it as an attribute
                    exec_globals[alias.name] = getattr(imported_module, alias.name)
                except AttributeError:
                    # If that fails, try importing the full module path
                    full_module_path = f"{module_name}.{alias.name}"
                    exec_globals[alias.name] = importlib.import_module(full_module_path)
        except ModuleNotFoundError as e:
            msg = f"Module {node.module} not found. Please install it and try again"
            raise ModuleNotFoundError(msg) from e

    if definitions:
        combined_module = ast.Module(body=definitions, type_ignores=[])
        compiled_code = compile(combined_module, "<string>", "exec")
        exec(compiled_code, exec_globals)

    return exec_globals


def extract_class_code(module, class_name):
    """Extracts the AST node for the specified class from the module."""
    class_code = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    class_code.parent = None
    return class_code


def compile_class_code(class_code):
    """Compiles the AST node of a class into a code object."""
    return compile(ast.Module(body=[class_code], type_ignores=[]), "<string>", "exec")


def build_class_constructor(compiled_class, exec_globals, class_name):
    """Builds a constructor function for the dynamically created class."""
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


def extract_class_name(code: str) -> str:
    """Extract the name of the first Component subclass found in the code."""
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


def unescape_string(s: str) -> str:
    """Replace escaped new line characters with actual new line characters."""
    return s.replace("\\n", "\n")


def sync_to_async(func):
    """Decorator to convert a sync function to an async function."""
    from functools import wraps

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return async_wrapper


def get_causing_exception(exc: BaseException) -> BaseException:
    """Get the causing exception from an exception."""
    if hasattr(exc, "__cause__") and exc.__cause__:
        return get_causing_exception(exc.__cause__)
    return exc


def format_syntax_error_message(exc: SyntaxError) -> str:
    """Format a SyntaxError message for returning to the frontend."""
    if exc.text is None:
        return f"Syntax error in code. Error on line {exc.lineno}"
    return f"Syntax error in code. Error on line {exc.lineno}: {exc.text.strip()}"


def format_exception_message(exc: Exception) -> str:
    """Format an exception message for returning to the frontend."""
    # We need to check if the __cause__ is a SyntaxError
    # If it is, we need to return the message of the SyntaxError
    causing_exception = get_causing_exception(exc)
    if isinstance(causing_exception, SyntaxError):
        return format_syntax_error_message(causing_exception)
    return str(exc)
