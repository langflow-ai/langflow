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


def get_class_doc(class_name):
    """
    Extracts information from the docstring of a given class.

    Args:
        class_name: the class to extract information from

    Returns:
        A dictionary containing the extracted information, with keys
        for 'Description', 'Parameters', 'Attributes', and 'Returns'.
    """
    # Get the class docstring
    docstring = class_name.__doc__

    # Parse the docstring to extract information
    lines = docstring.split("\n")
    data = {
        "Description": "",
        "Parameters": {},
        "Attributes": {},
        "Example": [],
        "Returns": {},
    }

    current_section = "Description"

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if (
            line.startswith(tuple(data.keys()))
            and len(line.split()) == 1
            and line.endswith(":")
        ):
            current_section = line[:-1]
            continue

        if current_section == "Description":
            data[current_section] += line
        elif current_section == "Example":
            data[current_section] += line
        else:
            try:
                param, desc = line.split(":")
            except:
                param, desc = "", ""
            data[current_section][param.strip()] = desc.strip()

    return data


# def format_dict(d):
#     # Remove from keys
#     keys_to_remove = ["callback_manager"]
#     for key in keys_to_remove:
#         if key in d:
#             d.pop(key)

#     for key, value in d.items():
#         _type = value["type"]

#         # Add optional parameter
#         if "Optional" in _type:
#             _type = _type.replace("Optional[", "")[:-1]

#         # Add list parameter
#         if "List" in _type:
#             _type = _type.replace("List[", "")[:-1]
#             value["list"] = True
#         else:
#             value["list"] = False

#         if "Mapping" in _type:
#             _type = _type.replace("Mapping", "dict")

#         value["type"] = _type

#         # Show if required
#         if value["required"] or key in ["allowed_tools", "verbose", "Memory"]:
#             value["show"] = True
#         else:
#             value["show"] = False

#         # If default, change to value
#         if value['type'] == 'str':
#             value["value"] = value["default"] if 'default' in value else ''
#             if 'default' in value:
#                 value.pop("default")

#     return {key: value for key, value in d.items() if value["show"]}


def format_dict(d):
    """
    Formats a dictionary by removing certain keys and modifying the values of other keys.

    Args:
        d: the dictionary to format

    Returns:
        A new dictionary with the desired modifications applied.
    """
    # Remove keys to exclude
    keys_to_exclude = ["callback_manager"]
    d = {key: value for key, value in d.items() if key not in keys_to_exclude}

    # Process remaining keys
    for key, value in d.items():
        _type = value["type"]

        # Remove 'Optional' wrapper
        if "Optional" in _type:
            _type = _type.replace("Optional[", "")[:-1]

        # Check for list type
        if "List" in _type:
            _type = _type.replace("List[", "")[:-1]
            value["list"] = True
        else:
            value["list"] = False

        # Replace 'Mapping' with 'dict'
        if "Mapping" in _type:
            _type = _type.replace("Mapping", "dict")

        value["type"] = _type

        # Show if required
        value["show"] = bool(
            value["required"] or key in ["allowed_tools", "verbose", "Memory"]
        )

        # Replace default value with actual value
        if _type == "str":
            value["value"] = value.get("default", "")
            if "default" in value:
                value.pop("default")

    # Filter out keys that should not be shown
    return {key: value for key, value in d.items() if value["show"]}
