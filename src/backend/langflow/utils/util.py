import importlib
import inspect
import re
from functools import wraps
from typing import Dict, Optional

from docstring_parser import parse  # type: ignore

from langflow.template.frontend_node.constants import FORCE_SHOW_FIELDS
from langflow.utils import constants


def build_template_from_function(
    name: str, type_to_loader_dict: Dict, add_function: bool = False
):
    classes = [
        item.__annotations__["return"].__name__ for item in type_to_loader_dict.values()
    ]

    # Raise error if name is not in chains
    if name not in classes:
        raise ValueError(f"{name} not found")

    for _type, v in type_to_loader_dict.items():
        if v.__annotations__["return"].__name__ == name:
            _class = v.__annotations__["return"]

            # Get the docstring
            docs = parse(_class.__doc__)

            variables = {"_type": _type}
            for class_field_items, value in _class.__fields__.items():
                if class_field_items in ["callback_manager"]:
                    continue
                variables[class_field_items] = {}
                for name_, value_ in value.__repr_args__():
                    if name_ == "default_factory":
                        try:
                            variables[class_field_items][
                                "default"
                            ] = get_default_factory(
                                module=_class.__base__.__module__, function=value_
                            )
                        except Exception:
                            variables[class_field_items]["default"] = None
                    elif name_ not in ["name"]:
                        variables[class_field_items][name_] = value_

                variables[class_field_items]["placeholder"] = (
                    docs.params[class_field_items]
                    if class_field_items in docs.params
                    else ""
                )
            # Adding function to base classes to allow
            # the output to be a function
            base_classes = get_base_classes(_class)
            if add_function:
                base_classes.append("function")

            return {
                "template": format_dict(variables, name),
                "description": docs.short_description or "",
                "base_classes": base_classes,
            }


def build_template_from_class(
    name: str, type_to_cls_dict: Dict, add_function: bool = False
):
    classes = [item.__name__ for item in type_to_cls_dict.values()]

    # Raise error if name is not in chains
    if name not in classes:
        raise ValueError(f"{name} not found.")

    for _type, v in type_to_cls_dict.items():
        if v.__name__ == name:
            _class = v

            # Get the docstring
            docs = parse(_class.__doc__)

            variables = {"_type": _type}

            if "__fields__" in _class.__dict__:
                for class_field_items, value in _class.__fields__.items():
                    if class_field_items in ["callback_manager"]:
                        continue
                    variables[class_field_items] = {}
                    for name_, value_ in value.__repr_args__():
                        if name_ == "default_factory":
                            try:
                                variables[class_field_items][
                                    "default"
                                ] = get_default_factory(
                                    module=_class.__base__.__module__, function=value_
                                )
                            except Exception:
                                variables[class_field_items]["default"] = None
                        elif name_ not in ["name"]:
                            variables[class_field_items][name_] = value_

                    variables[class_field_items]["placeholder"] = (
                        docs.params[class_field_items]
                        if class_field_items in docs.params
                        else ""
                    )
            base_classes = get_base_classes(_class)
            # Adding function to base classes to allow
            # the output to be a function
            if add_function:
                base_classes.append("function")
            return {
                "template": format_dict(variables, name),
                "description": docs.short_description or "",
                "base_classes": base_classes,
            }


def build_template_from_method(
    class_name: str,
    method_name: str,
    type_to_cls_dict: Dict,
    add_function: bool = False,
):
    classes = [item.__name__ for item in type_to_cls_dict.values()]

    # Raise error if class_name is not in classes
    if class_name not in classes:
        raise ValueError(f"{class_name} not found.")

    for _type, v in type_to_cls_dict.items():
        if v.__name__ == class_name:
            _class = v

            # Check if the method exists in this class
            if not hasattr(_class, method_name):
                raise ValueError(
                    f"Method {method_name} not found in class {class_name}"
                )

            # Get the method
            method = getattr(_class, method_name)

            # Get the docstring
            docs = parse(method.__doc__)

            # Get the signature of the method
            sig = inspect.signature(method)

            # Get the parameters of the method
            params = sig.parameters

            # Initialize the variables dictionary with method parameters
            variables = {
                "_type": _type,
                **{
                    name: {
                        "default": param.default
                        if param.default != param.empty
                        else None,
                        "type": param.annotation
                        if param.annotation != param.empty
                        else None,
                        "required": param.default == param.empty,
                    }
                    for name, param in params.items()
                },
            }

            base_classes = get_base_classes(_class)

            # Adding function to base classes to allow the output to be a function
            if add_function:
                base_classes.append("function")

            return {
                "template": format_dict(variables, class_name),
                "description": docs.short_description or "",
                "base_classes": base_classes,
            }


def get_base_classes(cls):
    """Get the base classes of a class.
    These are used to determine the output of the nodes.
    """
    if bases := cls.__bases__:
        result = []
        for base in bases:
            if any(type in base.__module__ for type in ["pydantic", "abc"]):
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
    return list(set(result + [cls.__name__]))


def get_default_factory(module: str, function: str):
    pattern = r"<function (\w+)>"

    if match := re.search(pattern, function):
        imported_module = importlib.import_module(module)
        return getattr(imported_module, match[1])()
    return None


def format_dict(d, name: Optional[str] = None):
    """
    Formats a dictionary by removing certain keys and modifying the
    values of other keys.

    Args:
        d: the dictionary to format
        name: the name of the class to format

    Returns:
        A new dictionary with the desired modifications applied.
    """

    # Process remaining keys
    for key, value in d.items():
        if key == "_type":
            continue

        _type = value["type"]

        # Remove 'Optional' wrapper
        if "Optional" in _type:
            _type = _type.replace("Optional[", "")[:-1]

        # Check for list type
        if "List" in _type or "Sequence" in _type or "Set" in _type:
            _type = _type.replace("List[", "")[:-1]
            value["list"] = True
        else:
            value["list"] = False

        # Replace 'Mapping' with 'dict'
        if "Mapping" in _type:
            _type = _type.replace("Mapping", "dict")

        # Change type from str to Tool
        value["type"] = "Tool" if key in ["allowed_tools"] else _type

        value["type"] = "int" if key in ["max_value_length"] else value["type"]

        # Show or not field
        value["show"] = bool(
            (value["required"] and key not in ["input_variables"])
            or key in FORCE_SHOW_FIELDS
            or "api_key" in key
        )

        # Add password field
        value["password"] = any(
            text in key.lower() for text in ["password", "token", "api", "key"]
        )

        # Add multline
        value["multiline"] = key in [
            "suffix",
            "prefix",
            "template",
            "examples",
            "code",
            "headers",
            "format_instructions",
        ]

        # Replace dict type with str
        if "dict" in value["type"].lower():
            value["type"] = "code"

        if key == "dict_":
            value["type"] = "file"
            value["suffixes"] = [".json", ".yaml", ".yml"]
            value["fileTypes"] = ["json", "yaml", "yml"]

        # Replace default value with actual value
        if "default" in value:
            value["value"] = value["default"]
            value.pop("default")

        if key == "headers":
            value[
                "value"
            ] = """{'Authorization':
            'Bearer <token>'}"""
        # Add options to openai
        if name == "OpenAI" and key == "model_name":
            value["options"] = constants.OPENAI_MODELS
            value["list"] = True
        elif name == "ChatOpenAI" and key == "model_name":
            value["options"] = constants.CHAT_OPENAI_MODELS
            value["list"] = True
        elif (name == "Anthropic" or name == "ChatAnthropic") and key == "model_name":
            value["options"] = constants.ANTHROPIC_MODELS
            value["list"] = True
    return d


def update_verbose(d: dict, new_value: bool) -> dict:
    """
    Recursively updates the value of the 'verbose' key in a dictionary.

    Args:
        d: the dictionary to update
        new_value: the new value to set

    Returns:
        The updated dictionary.
    """

    for k, v in d.items():
        if isinstance(v, dict):
            update_verbose(v, new_value)
        elif k == "verbose":
            d[k] = new_value
    return d


def sync_to_async(func):
    """
    Decorator to convert a sync function to an async function.
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return async_wrapper
