from pathlib import Path

from platformdirs import user_cache_dir


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


def is_valid_data(frontend_node, raw_frontend_data):
    """Check if the data is valid for processing."""

    return frontend_node and "template" in frontend_node and raw_frontend_data_is_valid(raw_frontend_data)


def update_template_values(frontend_template, raw_template):
    """Updates the frontend template with values from the raw template."""
    for key, value_dict in raw_template.items():
        if key == "code" or not isinstance(value_dict, dict):
            continue

        update_template_field(frontend_template, key, value_dict)


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

    old_code = raw_frontend_node["template"]["code"]["value"]
    new_code = frontend_node["template"]["code"]["value"]
    frontend_node["edited"] = old_code != new_code

    return frontend_node
