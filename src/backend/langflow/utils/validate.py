import ast
import contextlib
import importlib
import types
from typing import Dict


def add_type_ignores():
    if not hasattr(ast, "TypeIgnore"):

        class TypeIgnore(ast.AST):
            _fields = ()

        ast.TypeIgnore = TypeIgnore


def validate_code(code):
    # Initialize the errors dictionary
    errors = {"imports": {"errors": []}, "function": {"errors": []}}

    # Parse the code string into an abstract syntax tree (AST)
    try:
        tree = ast.parse(code)
    except Exception as e:
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
            code_obj = compile(
                ast.Module(body=[node], type_ignores=[]), "<string>", "exec"
            )
            try:
                exec(code_obj)
            except Exception as e:
                errors["function"]["errors"].append(str(e))

    # Return the errors dictionary
    return errors


def eval_function(function_string: str):
    # Create an empty dictionary to serve as a separate namespace
    namespace: Dict = {}

    # Execute the code string in the new namespace
    exec(function_string, namespace)
    function_object = next(
        (
            obj
            for name, obj in namespace.items()
            if isinstance(obj, types.FunctionType)
            and obj.__code__.co_filename == "<string>"
        ),
        None,
    )
    if function_object is None:
        raise ValueError("Function string does not contain a function")
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
                    exec_globals[alias.asname or alias.name] = importlib.import_module(
                        alias.name
                    )
                except ModuleNotFoundError as e:
                    raise ModuleNotFoundError(
                        f"Module {alias.name} not found. Please install it and try again."
                    ) from e

    function_code = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    function_code.parent = None
    code_obj = compile(
        ast.Module(body=[function_code], type_ignores=[]), "<string>", "exec"
    )
    try:
        exec(code_obj, exec_globals, locals())
    except Exception as exc:
        raise ValueError("Function string does not contain a function") from exc

    # Add the function to the exec_globals dictionary
    exec_globals[function_name] = locals()[function_name]

    return exec_globals[function_name](*args, **kwargs)


def create_function(code, function_name):
    if not hasattr(ast, "TypeIgnore"):

        class TypeIgnore(ast.AST):
            _fields = ()

        ast.TypeIgnore = TypeIgnore

    module = ast.parse(code)
    exec_globals = globals().copy()

    for node in module.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    exec_globals[alias.asname or alias.name] = importlib.import_module(
                        alias.name
                    )
                except ModuleNotFoundError as e:
                    raise ModuleNotFoundError(
                        f"Module {alias.name} not found. Please install it and try again."
                    ) from e

    function_code = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    function_code.parent = None
    code_obj = compile(
        ast.Module(body=[function_code], type_ignores=[]), "<string>", "exec"
    )
    with contextlib.suppress(Exception):
        exec(code_obj, exec_globals, locals())
    exec_globals[function_name] = locals()[function_name]

    # Return a function that imports necessary modules and calls the target function
    def wrapped_function(*args, **kwargs):
        for module_name, module in exec_globals.items():
            if isinstance(module, type(importlib)):
                globals()[module_name] = module

        return exec_globals[function_name](*args, **kwargs)

    return wrapped_function


def create_class(code, class_name):
    if not hasattr(ast, "TypeIgnore"):

        class TypeIgnore(ast.AST):
            _fields = ()

        ast.TypeIgnore = TypeIgnore

    module = ast.parse(code)
    exec_globals = globals().copy()

    for node in module.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    exec_globals[alias.asname or alias.name] = importlib.import_module(
                        alias.name
                    )
                except ModuleNotFoundError as e:
                    raise ModuleNotFoundError(
                        f"Module {alias.name} not found. Please install it and try again."
                    ) from e
        elif isinstance(node, ast.ImportFrom):
            try:
                imported_module = importlib.import_module(node.module)
                for alias in node.names:
                    exec_globals[alias.name] = getattr(imported_module, alias.name)
            except ModuleNotFoundError as e:
                raise ModuleNotFoundError(
                    f"Module {node.module} not found. Please install it and try again."
                ) from e

    class_code = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    class_code.parent = None
    code_obj = compile(
        ast.Module(body=[class_code], type_ignores=[]), "<string>", "exec"
    )
    # This suppresses import errors
    # with contextlib.suppress(Exception):
    exec(code_obj, exec_globals, locals())
    exec_globals[class_name] = locals()[class_name]

    # Return a function that imports necessary modules and creates an instance of the target class
    def build_my_class(*args, **kwargs):
        for module_name, module in exec_globals.items():
            if isinstance(module, type(importlib)):
                globals()[module_name] = module

        instance = exec_globals[class_name](*args, **kwargs)
        return instance

    build_my_class.__globals__.update(exec_globals)

    return build_my_class


def extract_function_name(code):
    module = ast.parse(code)
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            return node.name
    raise ValueError("No function definition found in the code string")


def extract_class_name(code):
    module = ast.parse(code)
    for node in module.body:
        if isinstance(node, ast.ClassDef):
            return node.name
    raise ValueError("No class definition found in the code string")
