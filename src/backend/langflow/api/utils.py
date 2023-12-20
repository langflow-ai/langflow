import warnings
from pathlib import Path
from typing import TYPE_CHECKING, List

from fastapi import HTTPException
from platformdirs import user_cache_dir

from langflow.services.store.schema import StoreComponentCreate
from langflow.services.store.utils import get_lf_version_from_pypi

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow


API_WORDS = ["api", "key", "token"]


def has_api_terms(word: str):
    return "api" in word and ("key" in word or ("token" in word and "tokens" not in word))


def remove_api_keys(flow: dict):
    """Remove api keys from flow data."""
    if flow.get("data") and flow["data"].get("nodes"):
        for node in flow["data"]["nodes"]:
            node_data = node.get("data").get("node")
            template = node_data.get("template")
            for value in template.values():
                if isinstance(value, dict) and has_api_terms(value["name"]) and value.get("password"):
                    value["value"] = None

    return flow


def build_input_keys_response(langchain_object, artifacts):
    """Build the input keys response."""

    input_keys_response = {
        "input_keys": {key: "" for key in langchain_object.input_keys},
        "memory_keys": [],
        "handle_keys": artifacts.get("handle_keys", []),
    }

    # Set the input keys values from artifacts
    for key, value in artifacts.items():
        if key in input_keys_response["input_keys"]:
            input_keys_response["input_keys"][key] = value
    # If the object has memory, that memory will have a memory_variables attribute
    # memory variables should be removed from the input keys
    if hasattr(langchain_object, "memory") and hasattr(langchain_object.memory, "memory_variables"):
        # Remove memory variables from input keys
        input_keys_response["input_keys"] = {
            key: value
            for key, value in input_keys_response["input_keys"].items()
            if key not in langchain_object.memory.memory_variables
        }
        # Add memory variables to memory_keys
        input_keys_response["memory_keys"] = langchain_object.memory.memory_variables

    if hasattr(langchain_object, "prompt") and hasattr(langchain_object.prompt, "template"):
        input_keys_response["template"] = langchain_object.prompt.template

    return input_keys_response


def update_frontend_node_with_template_values(frontend_node, raw_frontend_node):
    """
    Updates the given frontend node with values from the raw template data.

    :param frontend_node: A dict representing a built frontend node.
    :param raw_template_data: A dict representing raw template data.
    :return: Updated frontend node.
    """
    if not is_valid_data(frontend_node, raw_frontend_node):
        return frontend_node

    # Check if the display_name is different than "CustomComponent"
    # if so, update the display_name in the frontend_node
    if raw_frontend_node["display_name"] != "CustomComponent":
        frontend_node["display_name"] = raw_frontend_node["display_name"]

    update_template_values(frontend_node["template"], raw_frontend_node["template"])

    return frontend_node


def raw_frontend_data_is_valid(raw_frontend_data):
    """Check if the raw frontend data is valid for processing."""
    return "template" in raw_frontend_data and "display_name" in raw_frontend_data


def is_valid_data(frontend_node, raw_frontend_data):
    """Check if the data is valid for processing."""

    return frontend_node and "template" in frontend_node and raw_frontend_data_is_valid(raw_frontend_data)


def update_template_values(frontend_template, raw_template):
    """Updates the frontend template with values from the raw template."""
    for key, value_dict in raw_template.items():
        if key == "code" or not isinstance(value_dict, dict):
            continue

        update_template_field(frontend_template, key, value_dict)


def update_template_field(frontend_template, key, value_dict):
    """Updates a specific field in the frontend template."""
    template_field = frontend_template.get(key)
    if not template_field or template_field.get("type") != value_dict.get("type"):
        return

    if "value" in value_dict and value_dict["value"]:
        template_field["value"] = value_dict["value"]

    if "file_path" in value_dict and value_dict["file_path"]:
        file_path_value = get_file_path_value(value_dict["file_path"])
        if not file_path_value:
            # If the file does not exist, remove the value from the template_field["value"]
            template_field["value"] = ""
        template_field["file_path"] = file_path_value


def get_file_path_value(file_path):
    """Get the file path value if the file exists, else return empty string."""
    try:
        path = Path(file_path)
    except TypeError:
        return ""

    # Check for safety
    # If the path is not in the cache dir, return empty string
    # This is to prevent access to files outside the cache dir
    # If the path is not a file, return empty string
    if not path.exists() or not str(path).startswith(user_cache_dir("langflow", "langflow")):
        return ""
    return file_path


def validate_is_component(flows: List["Flow"]):
    for flow in flows:
        if not flow.data or flow.is_component is not None:
            continue

        is_component = get_is_component_from_data(flow.data)
        if is_component is not None:
            flow.is_component = is_component
        else:
            flow.is_component = len(flow.data.get("nodes", [])) == 1
    return flows


def get_is_component_from_data(data: dict):
    """Returns True if the data is a component."""
    return data.get("is_component")


async def check_langflow_version(component: StoreComponentCreate):
    from langflow import __version__ as current_version

    if not component.last_tested_version:
        component.last_tested_version = current_version

    langflow_version = get_lf_version_from_pypi()
    if langflow_version is None:
        raise HTTPException(status_code=500, detail="Unable to verify the latest version of Langflow")
    elif langflow_version != component.last_tested_version:
        warnings.warn(
            f"Your version of Langflow ({component.last_tested_version}) is outdated. "
            f"Please update to the latest version ({langflow_version}) and try again."
        )


def format_elapsed_time(elapsed_time) -> str:
    # Format elapsed time to human readable format coming from
    # perf_counter()
    # If the elapsed time is less than 1 second, return ms
    # If the elapsed time is less than 1 minute, return seconds rounded to 2 decimals
    time_str = ""
    if elapsed_time < 1:
        elapsed_time = int(round(elapsed_time * 1000))
        time_str = f"{elapsed_time} ms"
    elif elapsed_time < 60:
        elapsed_time = round(elapsed_time, 2)
        time_str = f"{elapsed_time} seconds"
    else:
        elapsed_time = round(elapsed_time / 60, 2)
        time_str = f"{elapsed_time} minutes"
    return time_str
