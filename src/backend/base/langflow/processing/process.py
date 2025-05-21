from __future__ import annotations

from typing import Any, cast

from loguru import logger
from pydantic import BaseModel

from langflow.processing.utils import validate_and_repair_json
from langflow.schema.graph import Tweaks


class Result(BaseModel):
    result: Any
    session_id: str


def validate_input(
    graph_data: dict[str, Any], tweaks: Tweaks | dict[str, str | dict[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(graph_data, dict) or not isinstance(tweaks, dict):
        msg = "graph_data and tweaks should be dictionaries"
        raise TypeError(msg)

    nodes = graph_data.get("data", {}).get("nodes") or graph_data.get("nodes")

    if not isinstance(nodes, list):
        msg = "graph_data should contain a list of nodes under 'data' key or directly under 'nodes' key"
        raise TypeError(msg)

    return nodes


def apply_tweaks(node: dict[str, Any], node_tweaks: dict[str, Any]) -> None:
    template_data = node.get("data", {}).get("node", {}).get("template")

    if not isinstance(template_data, dict):
        logger.warning(f"Template data for node {node.get('id')} should be a dictionary")
        return

    for tweak_name, tweak_value in node_tweaks.items():
        if tweak_name not in template_data:
            continue
        if tweak_name in template_data:
            if template_data[tweak_name]["type"] == "NestedDict":
                value = validate_and_repair_json(tweak_value)
                template_data[tweak_name]["value"] = value
            elif isinstance(tweak_value, dict):
                for k, v in tweak_value.items():
                    k_ = "file_path" if template_data[tweak_name]["type"] == "file" else k
                    template_data[tweak_name][k_] = v
            else:
                key = "file_path" if template_data[tweak_name]["type"] == "file" else "value"
                template_data[tweak_name][key] = tweak_value


def process_tweaks(
    graph_data: dict[str, Any], tweaks: Tweaks | dict[str, dict[str, Any]], *, stream: bool = False
) -> dict[str, Any]:
    """This function is used to tweak the graph data using the node id and the tweaks dict.

    :param graph_data: The dictionary containing the graph data. It must contain a 'data' key with
                       'nodes' as its child or directly contain 'nodes' key. Each node should have an 'id' and 'data'.
    :param tweaks: The dictionary containing the tweaks. The keys can be the node id or the name of the tweak.
                   The values can be a dictionary containing the tweaks for the node or the value of the tweak.
    :param stream: A boolean flag indicating whether streaming should be deactivated across all components or not.
                   Default is False.
    :return: The modified graph_data dictionary.
    :raises ValueError: If the input is not in the expected format.
    """
    tweaks_dict = cast("dict[str, Any]", tweaks.model_dump()) if not isinstance(tweaks, dict) else tweaks
    if "stream" not in tweaks_dict:
        tweaks_dict |= {"stream": stream}
    nodes = validate_input(graph_data, cast("dict[str, str | dict[str, Any]]", tweaks_dict))
    nodes_map = {node.get("id"): node for node in nodes}
    nodes_display_name_map = {node.get("data", {}).get("node", {}).get("display_name"): node for node in nodes}

    all_nodes_tweaks = {}
    for key, value in tweaks_dict.items():
        if isinstance(value, dict):
            if (node := nodes_map.get(key)) or (node := nodes_display_name_map.get(key)):
                apply_tweaks(node, value)
        else:
            all_nodes_tweaks[key] = value
    if all_nodes_tweaks:
        for node in nodes:
            apply_tweaks(node, all_nodes_tweaks)

    return graph_data
