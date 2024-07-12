import importlib
import inspect
import re
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from docstring_parser import parse

from langflow.schema import Data
from langflow.services.deps import get_settings_service
from langflow.template.frontend_node.constants import FORCE_SHOW_FIELDS
from langflow.utils import constants
from langflow.utils.logger import logger


def unescape_string(s: str):
    # Replace escaped new line characters with actual new line characters
    return s.replace("\\n", "\n")


def remove_ansi_escape_codes(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def build_template_from_function(name: str, type_to_loader_dict: Dict, add_function: bool = False):
    classes = [item.__annotations__["return"].__name__ for item in type_to_loader_dict.values()]

    # Raise error if name is not in chains
    if name not in classes:
        raise ValueError(f"{name} not found")

    for _type, v in type_to_loader_dict.items():
        if v.__annotations__["return"].__name__ == name:
            _class = v.__annotations__["return"]

            # Get the docstring
            docs = parse(_class.__doc__)

            variables = {"_type": _type}
            for class_field_items, value in _class.model_fields.items():
                if class_field_items in ["callback_manager"]:
                    continue
                variables[class_field_items] = {}
                for name_, value_ in value.__repr_args__():
                    if name_ == "default_factory":
                        try:
                            variables[class_field_items]["default"] = get_default_factory(
                                module=_class.__base__.__module__, function=value_
                            )
                        except Exception:
                            variables[class_field_items]["default"] = None
                    elif name_ not in ["name"]:
                        variables[class_field_items][name_] = value_

                variables[class_field_items]["placeholder"] = (
                    docs.params[class_field_items] if class_field_items in docs.params else ""
                )
            # Adding function to base classes to allow
            # the output to be a function
            base_classes = get_base_classes(_class)
            if add_function:
                base_classes.append("Callable")

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
                raise ValueError(f"Method {method_name} not found in class {class_name}")

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
                        "default": (param.default if param.default != param.empty else None),
                        "type": (param.annotation if param.annotation != param.empty else None),
                        "required": param.default == param.empty,
                    }
                    for name, param in params.items()
                    if name not in ["self", "kwargs", "args"]
                },
            }

            base_classes = get_base_classes(_class)

            # Adding function to base classes to allow the output to be a function
            if add_function:
                base_classes.append("Callable")

            return {
                "template": format_dict(variables, class_name),
                "description": docs.short_description or "",
                "base_classes": base_classes,
            }


def get_base_classes(cls):
    """Get the base classes of a class.
    These are used to determine the output of the nodes.
    """

    if hasattr(cls, "__bases__") and cls.__bases__:
        bases = cls.__bases__
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


def format_dict(dictionary: Dict[str, Any], class_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Formats a dictionary by removing certain keys and modifying the
    values of other keys.

    Returns:
        A new dictionary with the desired modifications applied.
    """

    for key, value in dictionary.items():
        if key in ["_type"]:
            continue

        _type: Union[str, type] = get_type(value)

        if "BaseModel" in str(_type):
            continue

        _type = remove_optional_wrapper(_type)
        _type = check_list_type(_type, value)
        _type = replace_mapping_with_dict(_type)
        _type = get_type_from_union_literal(_type)

        value["type"] = get_formatted_type(key, _type)
        value["show"] = should_show_field(value, key)
        value["password"] = is_password_field(key)
        value["multiline"] = is_multiline_field(key)

        if key == "dict_":
            set_dict_file_attributes(value)

        replace_default_value_with_actual(value)

        if key == "headers":
            set_headers_value(value)

        add_options_to_field(value, class_name, key)

    return dictionary


# "Union[Literal['f-string'], Literal['jinja2']]" -> "str"
def get_type_from_union_literal(union_literal: str) -> str:
    # if types are literal strings
    # the type is a string
    if "Literal" in union_literal:
        return "str"
    return union_literal


def get_type(value: Any) -> Union[str, type]:
    """
    Retrieves the type value from the dictionary.

    Returns:
        The type value.
    """
    # get "type" or "annotation" from the value
    _type = value.get("type") or value.get("annotation")

    return _type if isinstance(_type, str) else _type.__name__


def remove_optional_wrapper(_type: Union[str, type]) -> str:
    """
    Removes the 'Optional' wrapper from the type string.

    Returns:
        The type string with the 'Optional' wrapper removed.
    """
    if isinstance(_type, type):
        _type = str(_type)
    if "Optional" in _type:
        _type = _type.replace("Optional[", "")[:-1]

    return _type


def check_list_type(_type: str, value: Dict[str, Any]) -> str:
    """
    Checks if the type is a list type and modifies the value accordingly.

    Returns:
        The modified type string.
    """
    if any(list_type in _type for list_type in ["List", "Sequence", "Set"]):
        _type = _type.replace("List[", "").replace("Sequence[", "").replace("Set[", "")[:-1]
        value["list"] = True
    else:
        value["list"] = False

    return _type


def replace_mapping_with_dict(_type: str) -> str:
    """
    Replaces 'Mapping' with 'dict' in the type string.

    Returns:
        The modified type string.
    """
    if "Mapping" in _type:
        _type = _type.replace("Mapping", "dict")

    return _type


def get_formatted_type(key: str, _type: str) -> str:
    """
    Formats the type value based on the given key.

    Returns:
        The formatted type value.
    """
    if key == "allowed_tools":
        return "Tool"

    elif key == "max_value_length":
        return "int"

    return _type


def should_show_field(value: Dict[str, Any], key: str) -> bool:
    """
    Determines if the field should be shown or not.

    Returns:
        True if the field should be shown, False otherwise.
    """
    return (
        (value["required"] and key != "input_variables")
        or key in FORCE_SHOW_FIELDS
        or any(text in key.lower() for text in ["password", "token", "api", "key"])
    )


def is_password_field(key: str) -> bool:
    """
    Determines if the field is a password field.

    Returns:
        True if the field is a password field, False otherwise.
    """
    return any(text in key.lower() for text in ["password", "token", "api", "key"])


def is_multiline_field(key: str) -> bool:
    """
    Determines if the field is a multiline field.

    Returns:
        True if the field is a multiline field, False otherwise.
    """
    return key in {
        "suffix",
        "prefix",
        "template",
        "examples",
        "code",
        "headers",
        "format_instructions",
    }


def set_dict_file_attributes(value: Dict[str, Any]) -> None:
    """
    Sets the file attributes for the 'dict_' key.
    """
    value["type"] = "file"
    value["fileTypes"] = [".json", ".yaml", ".yml"]


def replace_default_value_with_actual(value: Dict[str, Any]) -> None:
    """
    Replaces the default value with the actual value.
    """
    if "default" in value:
        value["value"] = value["default"]
        value.pop("default")


def set_headers_value(value: Dict[str, Any]) -> None:
    """
    Sets the value for the 'headers' key.
    """
    value["value"] = """{"Authorization": "Bearer <token>"}"""


def add_options_to_field(value: Dict[str, Any], class_name: Optional[str], key: str) -> None:
    """
    Adds options to the field based on the class name and key.
    """
    options_map = {
        "OpenAI": constants.OPENAI_MODELS,
        "ChatOpenAI": constants.CHAT_OPENAI_MODELS,
        "Anthropic": constants.ANTHROPIC_MODELS,
        "ChatAnthropic": constants.ANTHROPIC_MODELS,
    }

    if class_name in options_map and key == "model_name":
        value["options"] = options_map[class_name]
        value["list"] = True
        value["value"] = options_map[class_name][0]


def build_loader_repr_from_data(data: List[Data]) -> str:
    """
    Builds a string representation of the loader based on the given data.

    Args:
        data (List[Data]): A list of data.

    Returns:
        str: A string representation of the loader.

    """
    if data:
        avg_length = sum(len(doc.text) for doc in data) / len(data)
        return f"""{len(data)} data
        \nAvg. Data Length (characters): {int(avg_length)}
        Data: {data[:3]}..."""
    return "0 data"


def update_settings(
    config: Optional[str] = None,
    cache: Optional[str] = None,
    dev: bool = False,
    remove_api_keys: bool = False,
    components_path: Optional[Path] = None,
    store: bool = True,
):
    """Update the settings from a config file."""
    from langflow.services.utils import initialize_settings_service

    # Check for database_url in the environment variables

    initialize_settings_service()
    settings_service = get_settings_service()
    if config:
        logger.debug(f"Loading settings from {config}")
        settings_service.settings.update_from_yaml(config, dev=dev)
    if remove_api_keys:
        logger.debug(f"Setting remove_api_keys to {remove_api_keys}")
        settings_service.settings.update_settings(remove_api_keys=remove_api_keys)
    if cache:
        logger.debug(f"Setting cache to {cache}")
        settings_service.settings.update_settings(cache=cache)
    if components_path:
        logger.debug(f"Adding component path {components_path}")
        settings_service.settings.update_settings(components_path=components_path)
    if not store:
        logger.debug("Setting store to False")
        settings_service.settings.update_settings(store=False)


def is_class_method(func, cls):
    """
    Check if a function is a class method.
    """
    return inspect.ismethod(func) and func.__self__ is cls.__class__
