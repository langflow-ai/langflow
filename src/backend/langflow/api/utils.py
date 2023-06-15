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
