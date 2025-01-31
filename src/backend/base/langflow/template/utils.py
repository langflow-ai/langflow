from pathlib import Path

from platformdirs import user_cache_dir

from langflow.schema.data import Data


def raw_frontend_data_is_valid(raw_frontend_data):
    """Check if the raw frontend data is valid for processing."""
    return "template" in raw_frontend_data and "display_name" in raw_frontend_data


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
    if not str(path).startswith(user_cache_dir("langflow", "langflow")):
        return ""

    if not path.exists():
        return ""
    return file_path


def update_template_field(new_template, key, previous_value_dict) -> None:
    """Updates a specific field in the frontend template."""
    template_field = new_template.get(key)
    if not template_field or template_field.get("type") != previous_value_dict.get("type"):
        return

    if "value" in previous_value_dict and previous_value_dict["value"] is not None:
        # if the new value is different, this means the default value has been changed
        # so we need to update the value in the template_field
        # and set other parameters to the new ones as well
        if template_field.get("value") != previous_value_dict["value"]:
            template_field["load_from_db"] = previous_value_dict.get("load_from_db", False)
        template_field["value"] = previous_value_dict["value"]

    if previous_value_dict.get("file_path"):
        file_path_value = get_file_path_value(previous_value_dict["file_path"])
        if not file_path_value:
            # If the file does not exist, remove the value from the template_field["value"]
            template_field["value"] = ""
        template_field["file_path"] = file_path_value


def is_valid_data(frontend_node, raw_frontend_data):
    """Check if the data is valid for processing."""
    return frontend_node and "template" in frontend_node and raw_frontend_data_is_valid(raw_frontend_data)


def update_template_values(new_template, previous_template) -> None:
    """Updates the frontend template with values from the raw template."""
    for key, previous_value_dict in previous_template.items():
        if key == "code" or not isinstance(previous_value_dict, dict):
            continue

        update_template_field(new_template, key, previous_value_dict)


def update_frontend_node_with_template_values(frontend_node, raw_frontend_node):
    """Updates the given frontend node with values from the raw template data.

    :param frontend_node: A dict representing a built frontend node.
    :param raw_template_data: A dict representing raw template data.
    :return: Updated frontend node.
    """
    if not is_valid_data(frontend_node, raw_frontend_node):
        return frontend_node

    update_template_values(frontend_node["template"], raw_frontend_node["template"])

    old_code = raw_frontend_node["template"]["code"]["value"]
    new_code = frontend_node["template"]["code"]["value"]
    frontend_node["edited"] = raw_frontend_node["edited"] or (old_code != new_code)
    frontend_node["tool_mode"] = raw_frontend_node.get("tool_mode", False)

    if any(extract_tool_modes(raw_frontend_node["template"])):
        frontend_node["tool_mode"] = False

    if not frontend_node.get("edited", False):
        frontend_node["display_name"] = raw_frontend_node["display_name"]
        frontend_node["description"] = raw_frontend_node["description"]

    return frontend_node


def extract_tool_modes(data: dict | list) -> list[bool | None]:
    tool_models = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "tool_mode":
                tool_models.append(value)
            else:
                tool_models.extend(extract_tool_modes(value))
    elif isinstance(data, list):
        for item in data:
            tool_models.extend(extract_tool_modes(item))

    return tool_models


def apply_json_filter(result, filter_):
    """Apply a json filter to the result.

    Args:
        result (Data): The JSON data to filter
        filter_ (str): The filter query string in jsonquery format

    Returns:
        Any: The filtered result
    """
    if not filter_ or not filter_.strip():
        return result
    # if result is a Data object, get the data
    if isinstance(result, Data):
        result = result.data
    try:
        from jsonquerylang import jsonquery

        # Convert result to string if it's a dict
        if isinstance(result, dict):
            import json

            result_str = json.dumps(result)
        else:
            result_str = str(result)

        # If query doesn't start with '.', add it to match jsonquery syntax
        query = filter_ if filter_.startswith(".") else f".{filter_}"
        return jsonquery(result_str, query)

    except (ImportError, ValueError, TypeError):
        # Fallback to basic path-based filtering
        # or if there's an error processing the query
        # Normalize array access notation and handle direct key access
        filter_str = filter_.strip()
        normalized_query = "." + filter_str if not filter_str.startswith(".") else filter_str
        normalized_query = normalized_query.replace("[", ".[")
        path = normalized_query.strip().split(".")
        path = [p for p in path if p]

        current = result
        for key in path:
            if current is None:
                return None

            # Handle array access
            if key.startswith("[") and key.endswith("]"):
                try:
                    index = int(key[1:-1])
                    if not isinstance(current, list) or index >= len(current):
                        return None
                    current = current[index]
                except (ValueError, TypeError):
                    return None
            # Handle object access
            elif isinstance(current, dict):
                if key not in current:
                    return None
                current = current[key]
            # Handle array operation
            elif isinstance(current, list):
                try:
                    current = [item[key] for item in current if isinstance(item, dict) and key in item]
                except (TypeError, KeyError):
                    return None
            else:
                return None

        return Data(data=current)
