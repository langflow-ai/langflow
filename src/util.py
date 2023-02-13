import ast
import inspect


def get_tool_params(func):
    # Parse the function code into an abstract syntax tree
    tree = ast.parse(inspect.getsource(func))

    # Iterate over the statements in the abstract syntax tree
    for node in ast.walk(tree):
        # Find the first return statement
        if isinstance(node, ast.Return):
            tool = node.value
            if isinstance(tool, ast.Call) and tool.func.id == "Tool":
                if tool.keywords:
                    tool_params = {}
                    for keyword in tool.keywords:
                        if keyword.arg == "name":
                            tool_params["name"] = ast.literal_eval(keyword.value)
                        elif keyword.arg == "description":
                            tool_params["description"] = ast.literal_eval(keyword.value)
                    return tool_params
                return {
                    "name": ast.literal_eval(tool.args[0]),
                    "description": ast.literal_eval(tool.args[2]),
                }

    # Return None if no return statement was found
    return None
