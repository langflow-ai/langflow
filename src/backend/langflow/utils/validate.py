import ast
import importlib
import types
from typing import Dict


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
    if not hasattr(ast, "TypeIgnore"):

        class TypeIgnore(ast.AST):
            _fields = ()

        ast.TypeIgnore = TypeIgnore
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
        (obj for name, obj in namespace.items() if isinstance(obj, types.FunctionType)),
        None,
    )
    if function_object is None:
        raise ValueError("Function string does not contain a function")
    return function_object
