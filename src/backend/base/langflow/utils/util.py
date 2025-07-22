import difflib
import importlib
import inspect
import json
import re
from functools import wraps
from pathlib import Path
from typing import Any

from docstring_parser import parse
from lfx.template.frontend_node.constants import FORCE_SHOW_FIELDS

from langflow.logging.logger import logger
from langflow.schema.data import Data
from langflow.services.deps import get_settings_service
from langflow.services.utils import initialize_settings_service
from langflow.utils import constants


def unescape_string(s: str):
    # Replace escaped new line characters with actual new line characters
    return s.replace("\\n", "\n")


def remove_ansi_escape_codes(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def build_template_from_function(name: str, type_to_loader_dict: dict, *, add_function: bool = False):
    classes = [item.__annotations__["return"].__name__ for item in type_to_loader_dict.values()]

    # Raise error if name is not in chains
    if name not in classes:
        msg = f"{name} not found"
        raise ValueError(msg)

    for _type, v in type_to_loader_dict.items():
        if v.__annotations__["return"].__name__ == name:
            class_ = v.__annotations__["return"]

            # Get the docstring
            docs = parse(class_.__doc__)

            variables = {"_type": _type}
            for class_field_items, value in class_.model_fields.items():
                if class_field_items == "callback_manager":
                    continue
                variables[class_field_items] = {}
                for name_, value_ in value.__repr_args__():
                    if name_ == "default_factory":
                        try:
                            variables[class_field_items]["default"] = get_default_factory(
                                module=class_.__base__.__module__, function=value_
                            )
                        except Exception:  # noqa: BLE001
                            logger.opt(exception=True).debug(f"Error getting default factory for {value_}")
                            variables[class_field_items]["default"] = None
                    elif name_ != "name":
                        variables[class_field_items][name_] = value_

                variables[class_field_items]["placeholder"] = docs.params.get(class_field_items, "")
            # Adding function to base classes to allow
            # the output to be a function
            base_classes = get_base_classes(class_)
            if add_function:
                base_classes.append("Callable")

            return {
                "template": format_dict(variables, name),
                "description": docs.short_description or "",
                "base_classes": base_classes,
            }
    return None


def build_template_from_method(
    class_name: str,
    method_name: str,
    type_to_cls_dict: dict,
    *,
    add_function: bool = False,
):
    classes = [item.__name__ for item in type_to_cls_dict.values()]

    # Raise error if class_name is not in classes
    if class_name not in classes:
        msg = f"{class_name} not found."
        raise ValueError(msg)

    for _type, v in type_to_cls_dict.items():
        if v.__name__ == class_name:
            class_ = v

            # Check if the method exists in this class
            if not hasattr(class_, method_name):
                msg = f"Method {method_name} not found in class {class_name}"
                raise ValueError(msg)

            # Get the method
            method = getattr(class_, method_name)

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
                    if name not in {"self", "kwargs", "args"}
                },
            }

            base_classes = get_base_classes(class_)

            # Adding function to base classes to allow the output to be a function
            if add_function:
                base_classes.append("Callable")

            return {
                "template": format_dict(variables, class_name),
                "description": docs.short_description or "",
                "base_classes": base_classes,
            }
    return None


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


def get_default_factory(module: str, function: str):
    pattern = r"<function (\w+)>"

    if match := re.search(pattern, function):
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="Support for class-based `config` is deprecated", category=DeprecationWarning
            )
            warnings.filterwarnings("ignore", message="Valid config keys have changed in V2", category=UserWarning)
            imported_module = importlib.import_module(module)
            return getattr(imported_module, match[1])()
    return None


def update_verbose(d: dict, *, new_value: bool) -> dict:
    """Recursively updates the value of the 'verbose' key in a dictionary.

    Args:
        d: the dictionary to update
        new_value: the new value to set

    Returns:
        The updated dictionary.
    """
    for k, v in d.items():
        if isinstance(v, dict):
            update_verbose(v, new_value=new_value)
        elif k == "verbose":
            d[k] = new_value
    return d


def sync_to_async(func):
    """Decorator to convert a sync function to an async function."""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return async_wrapper


def format_dict(dictionary: dict[str, Any], class_name: str | None = None) -> dict[str, Any]:
    """Formats a dictionary by removing certain keys and modifying the values of other keys.

    Returns:
        A new dictionary with the desired modifications applied.
    """
    for key, value in dictionary.items():
        if key == "_type":
            continue

        type_: str | type = get_type(value)

        if "BaseModel" in str(type_):
            continue

        type_ = remove_optional_wrapper(type_)
        type_ = check_list_type(type_, value)
        type_ = replace_mapping_with_dict(type_)
        type_ = get_type_from_union_literal(type_)

        value["type"] = get_formatted_type(key, type_)
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


def get_type(value: Any) -> str | type:
    """Retrieves the type value from the dictionary.

    Returns:
        The type value.
    """
    # get "type" or "annotation" from the value
    type_ = value.get("type") or value.get("annotation")

    return type_ if isinstance(type_, str) else type_.__name__


def remove_optional_wrapper(type_: str | type) -> str:
    """Removes the 'Optional' wrapper from the type string.

    Returns:
        The type string with the 'Optional' wrapper removed.
    """
    if isinstance(type_, type):
        type_ = str(type_)
    if "Optional" in type_:
        type_ = type_.replace("Optional[", "")[:-1]

    return type_


def check_list_type(type_: str, value: dict[str, Any]) -> str:
    """Checks if the type is a list type and modifies the value accordingly.

    Returns:
        The modified type string.
    """
    if any(list_type in type_ for list_type in ["List", "Sequence", "Set"]):
        type_ = type_.replace("List[", "").replace("Sequence[", "").replace("Set[", "")[:-1]
        value["list"] = True
    else:
        value["list"] = False

    return type_


def replace_mapping_with_dict(type_: str) -> str:
    """Replaces 'Mapping' with 'dict' in the type string.

    Returns:
        The modified type string.
    """
    if "Mapping" in type_:
        type_ = type_.replace("Mapping", "dict")

    return type_


def get_formatted_type(key: str, type_: str) -> str:
    """Formats the type value based on the given key.

    Returns:
        The formatted type value.
    """
    if key == "allowed_tools":
        return "Tool"

    if key == "max_value_length":
        return "int"

    return type_


def should_show_field(value: dict[str, Any], key: str) -> bool:
    """Determines if the field should be shown or not.

    Returns:
        True if the field should be shown, False otherwise.
    """
    return (
        (value["required"] and key != "input_variables")
        or key in FORCE_SHOW_FIELDS
        or any(text in key.lower() for text in ["password", "token", "api", "key"])
    )


def is_password_field(key: str) -> bool:
    """Determines if the field is a password field.

    Returns:
        True if the field is a password field, False otherwise.
    """
    return any(text in key.lower() for text in ["password", "token", "api", "key"])


def is_multiline_field(key: str) -> bool:
    """Determines if the field is a multiline field.

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


def set_dict_file_attributes(value: dict[str, Any]) -> None:
    """Sets the file attributes for the 'dict_' key."""
    value["type"] = "file"
    value["fileTypes"] = [".json", ".yaml", ".yml"]


def replace_default_value_with_actual(value: dict[str, Any]) -> None:
    """Replaces the default value with the actual value."""
    if "default" in value:
        value["value"] = value["default"]
        value.pop("default")


def set_headers_value(value: dict[str, Any]) -> None:
    """Sets the value for the 'headers' key."""
    value["value"] = """{"Authorization": "Bearer <token>"}"""


def add_options_to_field(value: dict[str, Any], class_name: str | None, key: str) -> None:
    """Adds options to the field based on the class name and key."""
    options_map = {
        "OpenAI": constants.OPENAI_MODELS,
        "ChatOpenAI": constants.CHAT_OPENAI_MODELS,
        "ReasoningOpenAI": constants.REASONING_OPENAI_MODELS,
        "Anthropic": constants.ANTHROPIC_MODELS,
        "ChatAnthropic": constants.ANTHROPIC_MODELS,
    }

    if class_name in options_map and key == "model_name":
        value["options"] = options_map[class_name]
        value["list"] = True
        value["value"] = options_map[class_name][0]


def build_loader_repr_from_data(data: list[Data]) -> str:
    """Builds a string representation of the loader based on the given data.

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


async def update_settings(
    *,
    config: str | None = None,
    cache: str | None = None,
    dev: bool = False,
    remove_api_keys: bool = False,
    components_path: Path | None = None,
    store: bool = True,
    auto_saving: bool = True,
    auto_saving_interval: int = 1000,
    health_check_max_retries: int = 5,
    max_file_size_upload: int = 100,
    webhook_polling_interval: int = 5000,
) -> None:
    """Update the settings from a config file."""
    # Check for database_url in the environment variables

    initialize_settings_service()
    settings_service = get_settings_service()
    if config:
        logger.debug(f"Loading settings from {config}")
        await settings_service.settings.update_from_yaml(config, dev=dev)
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
    if not auto_saving:
        logger.debug("Setting auto_saving to False")
        settings_service.settings.update_settings(auto_saving=False)
    if auto_saving_interval is not None:
        logger.debug(f"Setting auto_saving_interval to {auto_saving_interval}")
        settings_service.settings.update_settings(auto_saving_interval=auto_saving_interval)
    if health_check_max_retries is not None:
        logger.debug(f"Setting health_check_max_retries to {health_check_max_retries}")
        settings_service.settings.update_settings(health_check_max_retries=health_check_max_retries)
    if max_file_size_upload is not None:
        logger.debug(f"Setting max_file_size_upload to {max_file_size_upload}")
        settings_service.settings.update_settings(max_file_size_upload=max_file_size_upload)
    if webhook_polling_interval is not None:
        logger.debug(f"Setting webhook_polling_interval to {webhook_polling_interval}")
        settings_service.settings.update_settings(webhook_polling_interval=webhook_polling_interval)


def is_class_method(func, cls):
    """Check if a function is a class method."""
    return inspect.ismethod(func) and func.__self__ is cls.__class__


def escape_json_dump(edge_dict):
    return json.dumps(edge_dict).replace('"', "œ")


def find_closest_match(string: str, list_of_strings: list[str]) -> str | None:
    """Find the closest match in a list of strings."""
    closest_match = difflib.get_close_matches(string, list_of_strings, n=1, cutoff=0.2)
    if closest_match:
        return closest_match[0]
    return None
