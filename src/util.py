import ast
import inspect
import re
import importlib
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _LLM_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
)
from typing import Optional


def get_base_classes(cls):
    bases = cls.__bases__
    if not bases:
        return []
    else:
        result = []
        for base in bases:
            if any(type in base.__module__ for type in ["pydantic", "abc"]):
                continue
            result.append(base.__name__)
            result.extend(get_base_classes(base))
        return result


def get_default_factory(module: str, function: str):
    pattern = r"<function (\w+)>"

    if match := re.search(pattern, function):
        module = importlib.import_module(module)
        return getattr(module, match[1])()
    return None


def get_tools_dict(name: Optional[str] = None):
    """Get the tools dictionary."""
    tools = {
        **_BASE_TOOLS,
        **_LLM_TOOLS,
        **{k: v[0] for k, v in _EXTRA_LLM_TOOLS.items()},
        **{k: v[0] for k, v in _EXTRA_OPTIONAL_TOOLS.items()},
    }
    return tools[name] if name else tools


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

        if current_section in ["Description", "Example"]:
            data[current_section] += line
        else:
            param, desc = line.split(":")
            data[current_section][param.strip()] = desc.strip()

    return data


def format_dict(d):
    """
    Formats a dictionary by removing certain keys and modifying the
    values of other keys.

    Args:
        d: the dictionary to format

    Returns:
        A new dictionary with the desired modifications applied.
    """

    # Process remaining keys
    for key, value in d.items():
        if key == "examples":
            pass
        if key == "_type":
            continue
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

        value["type"] = "Tool" if key == "allowed_tools" else _type

        # Show if required
        value["show"] = bool(
            (value["required"] and key not in ["input_variables"])
            or key
            in ["allowed_tools", "verbose", "Memory", "memory", "prefix", "examples"]
            or "api_key" in key
        )

        # Add multline
        value["multline"] = key in ["suffix", "prefix", "template", "examples"]
        # Replace default value with actual value
        # if _type in ["str", "bool"]:
        #     value["value"] = value.get("default", "")
        #     if "default" in value:
        #         value.pop("default")
        if "default" in value:
            value["value"] = value["default"]
            value.pop("default")

    # Filter out keys that should not be shown
    return d
