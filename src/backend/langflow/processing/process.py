import json
from pathlib import Path
from langchain.schema import AgentAction
from langflow.interface.run import (
    build_sorted_vertices,
    get_memory_key,
    update_memory_keys,
)
from langflow.services.getters import get_session_service
from loguru import logger
from langflow.graph import Graph
from langchain.chains.base import Chain
from langchain.vectorstores.base import VectorStore
from typing import Any, Dict, List, Optional, Tuple, Union
from langchain.schema import Document

from pydantic import BaseModel


def fix_memory_inputs(langchain_object):
    """
    Given a LangChain object, this function checks if it has a memory attribute and if that memory key exists in the
    object's input variables. If so, it does nothing. Otherwise, it gets a possible new memory key using the
    get_memory_key function and updates the memory keys using the update_memory_keys function.
    """
    if not hasattr(langchain_object, "memory") or langchain_object.memory is None:
        return
    try:
        if (
            hasattr(langchain_object.memory, "memory_key")
            and langchain_object.memory.memory_key in langchain_object.input_variables
        ):
            return
    except AttributeError:
        input_variables = (
            langchain_object.prompt.input_variables
            if hasattr(langchain_object, "prompt")
            else langchain_object.input_keys
        )
        if langchain_object.memory.memory_key in input_variables:
            return

    possible_new_mem_key = get_memory_key(langchain_object)
    if possible_new_mem_key is not None:
        update_memory_keys(langchain_object, possible_new_mem_key)


def format_actions(actions: List[Tuple[AgentAction, str]]) -> str:
    """Format a list of (AgentAction, answer) tuples into a string."""
    output = []
    for action, answer in actions:
        log = action.log
        tool = action.tool
        tool_input = action.tool_input
        output.append(f"Log: {log}")
        if "Action" not in log and "Action Input" not in log:
            output.append(f"Tool: {tool}")
            output.append(f"Tool Input: {tool_input}")
        output.append(f"Answer: {answer}")
        output.append("")  # Add a blank line
    return "\n".join(output)


def get_result_and_thought(langchain_object: Any, inputs: dict):
    """Get result and thought from extracted json"""
    try:
        if hasattr(langchain_object, "verbose"):
            langchain_object.verbose = True

        if hasattr(langchain_object, "return_intermediate_steps"):
            langchain_object.return_intermediate_steps = False

        fix_memory_inputs(langchain_object)

        try:
            output = langchain_object(inputs, return_only_outputs=True)
        except ValueError as exc:
            # make the error message more informative
            logger.debug(f"Error: {str(exc)}")
            output = langchain_object.run(inputs)

    except Exception as exc:
        raise ValueError(f"Error: {str(exc)}") from exc
    return output


def get_input_str_if_only_one_input(inputs: dict) -> Optional[str]:
    """Get input string if only one input is provided"""
    return list(inputs.values())[0] if len(inputs) == 1 else None


def get_build_result(data_graph, session_id):
    # If session_id is provided, load the langchain_object from the session
    # using build_sorted_vertices_with_caching.get_result_by_session_id
    # if it returns something different than None, return it
    # otherwise, build the graph and return the result
    if session_id:
        logger.debug(f"Loading LangChain object from session {session_id}")
        result = build_sorted_vertices(data_graph=data_graph)
        if result is not None:
            logger.debug("Loaded LangChain object")
            return result

    logger.debug("Building langchain object")
    return build_sorted_vertices(data_graph)


def load_langchain_object(
    data_graph: Dict[str, Any], session_id: str
) -> Tuple[Union[Chain, VectorStore], Dict[str, Any], str]:
    langchain_object, artifacts = get_build_result(data_graph, session_id)
    logger.debug("Loaded LangChain object")

    if langchain_object is None:
        raise ValueError(
            "There was an error loading the langchain_object. Please, check all the nodes and try again."
        )

    return langchain_object, artifacts, session_id


def process_inputs(inputs: Optional[dict], artifacts: Dict[str, Any]) -> dict:
    if inputs is None:
        inputs = {}

    for key, value in artifacts.items():
        if key not in inputs or not inputs[key]:
            inputs[key] = value

    return inputs


def generate_result(langchain_object: Union[Chain, VectorStore], inputs: dict):
    if isinstance(langchain_object, Chain):
        if inputs is None:
            raise ValueError("Inputs must be provided for a Chain")
        logger.debug("Generating result and thought")
        result = get_result_and_thought(langchain_object, inputs)

        logger.debug("Generated result and thought")
    elif isinstance(langchain_object, VectorStore):
        result = langchain_object.search(**inputs)
    elif isinstance(langchain_object, Document):
        result = langchain_object.dict()
    else:
        logger.warning(f"Unknown langchain_object type: {type(langchain_object)}")
        result = langchain_object

    return result


class Result(BaseModel):
    result: Any
    session_id: str


async def process_graph_cached(
    data_graph: Dict[str, Any],
    inputs: Optional[dict] = None,
    clear_cache=False,
    session_id=None,
) -> Result:
    session_service = get_session_service()
    if clear_cache:
        session_service.clear_session(session_id)
    if session_id is None:
        session_id = session_service.generate_key(
            session_id=session_id, data_graph=data_graph
        )
    # Load the graph using SessionService
    graph, artifacts = session_service.load_session(session_id, data_graph)
    built_object = graph.build()
    processed_inputs = process_inputs(inputs, artifacts)
    result = generate_result(built_object, processed_inputs)
    # langchain_object is now updated with the new memory
    # we need to update the cache with the updated langchain_object
    session_service.update_session(session_id, (graph, artifacts))

    return Result(result=result, session_id=session_id)


def load_flow_from_json(
    flow: Union[Path, str, dict], tweaks: Optional[dict] = None, build=True
):
    """
    Load flow from a JSON file or a JSON object.

    :param flow: JSON file path or JSON object
    :param tweaks: Optional tweaks to be processed
    :param build: If True, build the graph, otherwise return the graph object
    :return: Langchain object or Graph object depending on the build parameter
    """
    # If input is a file path, load JSON from the file
    if isinstance(flow, (str, Path)):
        with open(flow, "r", encoding="utf-8") as f:
            flow_graph = json.load(f)
    # If input is a dictionary, assume it's a JSON object
    elif isinstance(flow, dict):
        flow_graph = flow
    else:
        raise TypeError(
            "Input must be either a file path (str) or a JSON object (dict)"
        )

    graph_data = flow_graph["data"]
    if tweaks is not None:
        graph_data = process_tweaks(graph_data, tweaks)
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]
    graph = Graph(nodes, edges)

    if build:
        langchain_object = graph.build()

        if hasattr(langchain_object, "verbose"):
            langchain_object.verbose = True

        if hasattr(langchain_object, "return_intermediate_steps"):
            # Deactivating until we have a frontend solution
            # to display intermediate steps
            langchain_object.return_intermediate_steps = False

        fix_memory_inputs(langchain_object)
        return langchain_object

    return graph


def validate_input(
    graph_data: Dict[str, Any], tweaks: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not isinstance(graph_data, dict) or not isinstance(tweaks, dict):
        raise ValueError("graph_data and tweaks should be dictionaries")

    nodes = graph_data.get("data", {}).get("nodes") or graph_data.get("nodes")

    if not isinstance(nodes, list):
        raise ValueError(
            "graph_data should contain a list of nodes under 'data' key or directly under 'nodes' key"
        )

    return nodes


def apply_tweaks(node: Dict[str, Any], node_tweaks: Dict[str, Any]) -> None:
    template_data = node.get("data", {}).get("node", {}).get("template")

    if not isinstance(template_data, dict):
        logger.warning(
            f"Template data for node {node.get('id')} should be a dictionary"
        )
        return

    for tweak_name, tweak_value in node_tweaks.items():
        if tweak_name and tweak_value and tweak_name in template_data:
            key = tweak_name if tweak_name == "file_path" else "value"
            template_data[tweak_name][key] = tweak_value


def process_tweaks(
    graph_data: Dict[str, Any], tweaks: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    This function is used to tweak the graph data using the node id and the tweaks dict.

    :param graph_data: The dictionary containing the graph data. It must contain a 'data' key with
                       'nodes' as its child or directly contain 'nodes' key. Each node should have an 'id' and 'data'.
    :param tweaks: A dictionary where the key is the node id and the value is a dictionary of the tweaks.
                   The inner dictionary contains the name of a certain parameter as the key and the value to be tweaked.

    :return: The modified graph_data dictionary.

    :raises ValueError: If the input is not in the expected format.
    """
    nodes = validate_input(graph_data, tweaks)

    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("id"), str):
            node_id = node["id"]
            if node_tweaks := tweaks.get(node_id):
                apply_tweaks(node, node_tweaks)
        else:
            logger.warning(
                "Each node should be a dictionary with an 'id' key of type str"
            )

    return graph_data
