import ast
import inspect
from typing import Dict, Union

from langchain.agents.tools import Tool


def get_func_tool_params(func, **kwargs) -> Union[Dict, None]:
    tree = ast.parse(inspect.getsource(func))

    # Iterate over the statements in the abstract syntax tree
    for node in ast.walk(tree):
        # Find the first return statement
        if isinstance(node, ast.Return):
            tool = node.value
            if isinstance(tool, ast.Call):
                if isinstance(tool.func, ast.Name) and tool.func.id == "Tool":
                    if tool.keywords:
                        tool_params = {}
                        for keyword in tool.keywords:
                            if keyword.arg == "name":
                                try:
                                    tool_params["name"] = ast.literal_eval(
                                        keyword.value
                                    )
                                except ValueError:
                                    break
                            elif keyword.arg == "description":
                                try:
                                    tool_params["description"] = ast.literal_eval(
                                        keyword.value
                                    )
                                except ValueError:
                                    continue

                        return tool_params
                    return {
                        "name": ast.literal_eval(tool.args[0]),
                        "description": ast.literal_eval(tool.args[2]),
                    }
                #
                else:
                    # get the class object from the return statement
                    try:
                        class_obj = eval(
                            compile(ast.Expression(tool), "<string>", "eval")
                        )
                    except Exception:
                        return None

                    return {
                        "name": getattr(class_obj, "name"),
                        "description": getattr(class_obj, "description"),
                    }
        # Return None if no return statement was found
    return None


def get_class_tool_params(cls, **kwargs) -> Union[Dict, None]:
    tree = ast.parse(inspect.getsource(cls))

    tool_params = {}

    # Iterate over the statements in the abstract syntax tree
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Find the class definition and look for methods
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__":
                    # There is no assignment statements in the __init__ method
                    # So we need to get the params from the function definition
                    for arg in stmt.args.args:
                        if arg.arg == "name":
                            # It should be the name of the class
                            tool_params[arg.arg] = cls.__name__
                        elif arg.arg == "self":
                            continue
                        # If there is not default value, set it to an empty string
                        else:
                            try:
                                annotation = ast.literal_eval(arg.annotation)  # type: ignore
                                tool_params[arg.arg] = annotation
                            except ValueError:
                                tool_params[arg.arg] = ""
                # Get the attribute name and the annotation
                elif cls != Tool and isinstance(stmt, ast.AnnAssign):
                    # Get the attribute name and the annotation
                    tool_params[stmt.target.id] = ""  # type: ignore

    return tool_params


def get_tool_params(tool, **kwargs) -> Dict:
    # Parse the function code into an abstract syntax tree
    # Define if it is a function or a class
    if inspect.isfunction(tool):
        return get_func_tool_params(tool, **kwargs) or {}
    elif inspect.isclass(tool):
        # Get the parameters necessary to
        # instantiate the class

        return get_class_tool_params(tool, **kwargs) or {}

    else:
        raise ValueError("Tool must be a function or class.")
