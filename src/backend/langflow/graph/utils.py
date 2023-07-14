from collections import defaultdict
import re
from typing import Any, Union


def validate_prompt(prompt: str):
    """Validate prompt."""
    if extract_input_variables_from_prompt(prompt):
        return prompt

    return fix_prompt(prompt)


def fix_prompt(prompt: str):
    """Fix prompt."""
    return prompt + " {input}"


def extract_input_variables_from_prompt(prompt: str) -> list[str]:
    """Extract input variables from prompt."""
    return re.findall(r"{(.*?)}", prompt)


def get_proxy_values(template):
    proxy_cache = defaultdict(dict)
    for value_dict in template.values():
        if proxy := value_dict.get("proxy"):
            proxy_cache[proxy["id"]][proxy["field"]] = value_dict.get("value")
    return proxy_cache


# Now I need to iterate over the nodes and replace the proxy values with the values from the cache
def set_proxy_values(group_node, proxy_cache):
    inner_nodes = group_node["flow"]["data"]["nodes"]
    for node in inner_nodes:
        if proxy_values := proxy_cache.get(node["id"]):
            for key, value in proxy_values.items():
                node["data"]["node"]["template"][key]["value"] = value


def flatten_list(list_of_lists: list[Union[list, Any]]) -> list:
    """Flatten list of lists."""
    new_list = []
    for item in list_of_lists:
        if isinstance(item, list):
            new_list.extend(item)
        else:
            new_list.append(item)
    return new_list
