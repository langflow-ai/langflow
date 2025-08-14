from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from json_repair import repair_json
from loguru import logger
from pydantic import BaseModel

from lfx.graph.vertex.base import Vertex
from lfx.schema.graph import InputValue, Tweaks
from lfx.schema.schema import INPUT_FIELD_NAME, InputValueRequest
from lfx.services.deps import get_settings_service

if TYPE_CHECKING:
    from lfx.events.event_manager import EventManager
    from lfx.graph.graph.base import Graph
    from lfx.graph.schema import RunOutputs


def validate_and_repair_json(json_str: str | dict) -> dict[str, Any] | str:
    """Validates a JSON string and attempts to repair it if invalid.

    Args:
        json_str (str): The JSON string to validate/repair

    Returns:
        Union[Dict[str, Any], str]: The parsed JSON dict if valid/repairable,
        otherwise returns the original string
    """
    if not isinstance(json_str, str):
        return json_str
    try:
        # If invalid, attempt repair
        repaired = repair_json(json_str)
        return json.loads(repaired)
    except (json.JSONDecodeError, ImportError):
        # Return original if repair fails or module not found
        return json_str


class Result(BaseModel):
    result: Any
    session_id: str


async def run_graph_internal(
    graph: Graph,
    flow_id: str,
    *,
    stream: bool = False,
    session_id: str | None = None,
    inputs: list[InputValueRequest] | None = None,
    outputs: list[str] | None = None,
    event_manager: EventManager | None = None,
) -> tuple[list[RunOutputs], str]:
    """Run the graph and generate the result."""
    inputs = inputs or []
    effective_session_id = session_id or flow_id
    components = []
    inputs_list = []
    types = []
    for input_value_request in inputs:
        if input_value_request.input_value is None:
            logger.warning("InputValueRequest input_value cannot be None, defaulting to an empty string.")
            input_value_request.input_value = ""
        components.append(input_value_request.components or [])
        inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value})
        types.append(input_value_request.type)

    try:
        fallback_to_env_vars = get_settings_service().settings.fallback_to_env_var
    except (AttributeError, TypeError):
        fallback_to_env_vars = False

    graph.session_id = effective_session_id
    run_outputs = await graph.arun(
        inputs=inputs_list,
        inputs_components=components,
        types=types,
        outputs=outputs or [],
        stream=stream,
        session_id=effective_session_id or "",
        fallback_to_env_vars=fallback_to_env_vars,
        event_manager=event_manager,
    )
    return run_outputs, effective_session_id


async def run_graph(
    graph: Graph,
    input_value: str,
    input_type: str,
    output_type: str,
    *,
    session_id: str | None = None,
    fallback_to_env_vars: bool = False,
    output_component: str | None = None,
    stream: bool = False,
) -> list[RunOutputs]:
    """Runs the given Langflow Graph with the specified input and returns the outputs.

    Args:
        graph (Graph): The graph to be executed.
        input_value (str): The input value to be passed to the graph.
        input_type (str): The type of the input value.
        output_type (str): The type of the desired output.
        session_id (str | None, optional): The session ID to be used for the flow. Defaults to None.
        fallback_to_env_vars (bool, optional): Whether to fallback to environment variables.
            Defaults to False.
        output_component (Optional[str], optional): The specific output component to retrieve. Defaults to None.
        stream (bool, optional): Whether to stream the results or not. Defaults to False.

    Returns:
        List[RunOutputs]: A list of RunOutputs objects representing the outputs of the graph.

    """
    inputs = [InputValue(components=[], input_value=input_value, type=input_type)]
    if output_component:
        outputs = [output_component]
    else:
        outputs = [
            vertex.id
            for vertex in graph.vertices
            if output_type == "debug"
            or (vertex.is_output and (output_type == "any" or output_type in vertex.id.lower()))
        ]
    components = []
    inputs_list = []
    types = []
    for input_value_request in inputs:
        if input_value_request.input_value is None:
            logger.warning("InputValueRequest input_value cannot be None, defaulting to an empty string.")
            input_value_request.input_value = ""
        components.append(input_value_request.components or [])
        inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value})
        types.append(input_value_request.type)
    return await graph.arun(
        inputs_list,
        inputs_components=components,
        types=types,
        outputs=outputs or [],
        stream=stream,
        session_id=session_id,
        fallback_to_env_vars=fallback_to_env_vars,
    )


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


def apply_tweaks_on_vertex(vertex: Vertex, node_tweaks: dict[str, Any]) -> None:
    for tweak_name, tweak_value in node_tweaks.items():
        if tweak_name and tweak_value and tweak_name in vertex.params:
            vertex.params[tweak_name] = tweak_value


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


def process_tweaks_on_graph(graph: Graph, tweaks: dict[str, dict[str, Any]]):
    for vertex in graph.vertices:
        if isinstance(vertex, Vertex) and isinstance(vertex.id, str):
            node_id = vertex.id
            if node_tweaks := tweaks.get(node_id):
                apply_tweaks_on_vertex(vertex, node_tweaks)
        else:
            logger.warning("Each node should be a Vertex with an 'id' attribute of type str")

    return graph
