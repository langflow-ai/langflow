API_WORDS = ["api", "key", "token"]


def has_api_terms(word: str):
    return "api" in word and (
        "key" in word or ("token" in word and "tokens" not in word)
    )


def remove_api_keys(flow: dict):
    """Remove api keys from flow data."""
    if flow.get("data") and flow["data"].get("nodes"):
        for node in flow["data"]["nodes"]:
            node_data = node.get("data").get("node")
            template = node_data.get("template")
            for value in template.values():
                if (
                    isinstance(value, dict)
                    and has_api_terms(value["name"])
                    and value.get("password")
                ):
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
    if hasattr(langchain_object, "memory") and hasattr(
        langchain_object.memory, "memory_variables"
    ):
        # Remove memory variables from input keys
        input_keys_response["input_keys"] = {
            key: value
            for key, value in input_keys_response["input_keys"].items()
            if key not in langchain_object.memory.memory_variables
        }
        # Add memory variables to memory_keys
        input_keys_response["memory_keys"] = langchain_object.memory.memory_variables

    if hasattr(langchain_object, "prompt") and hasattr(
        langchain_object.prompt, "template"
    ):
        input_keys_response["template"] = langchain_object.prompt.template

    return input_keys_response


def get_new_key(dictionary, original_key):
    counter = 1
    new_key = original_key + " (" + str(counter) + ")"
    while new_key in dictionary:
        counter += 1
        new_key = original_key + " (" + str(counter) + ")"
    return new_key
