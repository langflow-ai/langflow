from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


def build_clean_params(target: "Vertex") -> dict:
    """
    Cleans the parameters of the target vertex.
    """
    # Removes all keys that the values aren't python types like str, int, bool, etc.
    params = {
        key: value for key, value in target.params.items() if isinstance(value, (str, int, bool, float, list, dict))
    }
    # if it is a list we need to check if the contents are python types
    for key, value in params.items():
        if isinstance(value, list):
            params[key] = [item for item in value if isinstance(item, (str, int, bool, float, list, dict))]
    return params
