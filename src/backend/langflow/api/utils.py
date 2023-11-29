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


def update_frontend_node_with_template_values(frontend_node, raw_template_data):
    """
    Updates the given frontend node with values from the raw template data.

    :param frontend_node: A dict representing a built frontend node.
    :param raw_template_data: A dict representing raw template data.
    :return: Updated frontend node.
    """
    if (
        not frontend_node
        or "template" not in frontend_node
        or not raw_template_data
        or not raw_template_data.template
    ):
        return frontend_node

    frontend_template = frontend_node.get("template", {})
    raw_template = raw_template_data.template or {}

    for key, value_dict in raw_template.items():
        if key == "code" or not isinstance(value_dict, dict):
            continue

        value = value_dict.get("value")
        template_field_type = value_dict.get("type")
        frontend_node_field_type = frontend_template[key].get("type")
        if value is not None and key in frontend_template and template_field_type == frontend_node_field_type:
            frontend_template[key]["value"] = value

    return frontend_node
