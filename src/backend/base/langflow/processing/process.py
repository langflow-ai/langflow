from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union


from langchain.agents import AgentExecutor
from langchain.schema import AgentAction
from loguru import logger
from pydantic import BaseModel

from langflow.graph.graph.base import Graph
from langflow.graph.schema import RunOutputs
from langflow.graph.vertex.base import Vertex
from langflow.interface.run import get_memory_key, update_memory_keys
from langflow.schema.graph import InputValue, Tweaks
from langflow.schema.schema import INPUT_FIELD_NAME
from langflow.services.session.service import SessionService


if TYPE_CHECKING:
    from langflow.api.v1.schemas import InputValueRequest


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

        try:
            if not isinstance(langchain_object, AgentExecutor):
                fix_memory_inputs(langchain_object)
        except Exception as exc:
            logger.error(f"Error fixing memory inputs: {exc}")

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


def process_inputs(
    inputs: Optional[Union[dict, List[dict]]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
) -> Union[dict, List[dict]]:
    if inputs is None:
        inputs = {}
    if artifacts is None:
        artifacts = {}

    if isinstance(inputs, dict):
        inputs = update_inputs_dict(inputs, artifacts)
    elif isinstance(inputs, List):
        inputs = [update_inputs_dict(inp, artifacts) for inp in inputs]

    return inputs


def update_inputs_dict(inputs: dict, artifacts: Dict[str, Any]) -> dict:
    for key, value in artifacts.items():
        if key == "repr":
            continue
        elif key not in inputs or not inputs[key]:
            inputs[key] = value

    return inputs


class Result(BaseModel):
    result: Any
    session_id: str


async def run_graph_internal(
    graph: "Graph",
    flow_id: str,
    stream: bool = False,
    session_id: Optional[str] = None,
    inputs: Optional[List["InputValueRequest"]] = None,
    outputs: Optional[List[str]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
    session_service: Optional[SessionService] = None,
) -> tuple[List[RunOutputs], str]:
    """Run the graph and generate the result"""
    inputs = inputs or []
    graph_data = graph._graph_data
    if session_id is None and session_service is not None:
        session_id_str = session_service.generate_key(session_id=flow_id, data_graph=graph_data)
    elif session_id is not None:
        session_id_str = session_id
    else:
        raise ValueError("session_id or session_service must be provided")
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

    run_outputs = await graph.arun(
        inputs_list,
        components,
        types,
        outputs or [],
        stream=stream,
        session_id=session_id_str or "",
    )
    if session_id_str and session_service:
        await session_service.update_session(session_id_str, (graph, artifacts))
    return run_outputs, session_id_str


def run_graph(
    graph: "Graph",
    input_value: str,
    input_type: str,
    output_type: str,
    output_component: Optional[str] = None,
) -> List[RunOutputs]:
    """
    Runs the given Langflow Graph with the specified input and returns the outputs.

    Args:
        graph (Graph): The graph to be executed.
        input_value (str): The input value to be passed to the graph.
        input_type (str): The type of the input value.
        output_type (str): The type of the desired output.
        output_component (Optional[str], optional): The specific output component to retrieve. Defaults to None.

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
    run_outputs = graph.run(
        inputs_list,
        components,
        types,
        outputs or [],
        stream=False,
        session_id="",
    )
    return run_outputs


def validate_input(
    graph_data: Dict[str, Any], tweaks: Union["Tweaks", Dict[str, Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    if not isinstance(graph_data, dict) or not isinstance(tweaks, dict):
        raise ValueError("graph_data and tweaks should be dictionaries")

    nodes = graph_data.get("data", {}).get("nodes") or graph_data.get("nodes")

    if not isinstance(nodes, list):
        raise ValueError("graph_data should contain a list of nodes under 'data' key or directly under 'nodes' key")

    return nodes


def apply_tweaks(node: Dict[str, Any], node_tweaks: Dict[str, Any]) -> None:
    template_data = node.get("data", {}).get("node", {}).get("template")

    if not isinstance(template_data, dict):
        logger.warning(f"Template data for node {node.get('id')} should be a dictionary")
        return

    for tweak_name, tweak_value in node_tweaks.items():
        if tweak_name not in template_data:
            continue
        if tweak_name in template_data:
            key = "file_path" if template_data[tweak_name]["type"] == "file" else "value"
            template_data[tweak_name][key] = tweak_value


def apply_tweaks_on_vertex(vertex: Vertex, node_tweaks: Dict[str, Any]) -> None:
    for tweak_name, tweak_value in node_tweaks.items():
        if tweak_name and tweak_value and tweak_name in vertex.params:
            vertex.params[tweak_name] = tweak_value


def process_tweaks(
    graph_data: Dict[str, Any], tweaks: Union["Tweaks", Dict[str, Dict[str, Any]]], stream: bool = False
) -> Dict[str, Any]:
    """
    This function is used to tweak the graph data using the node id and the tweaks dict.

    :param graph_data: The dictionary containing the graph data. It must contain a 'data' key with
                       'nodes' as its child or directly contain 'nodes' key. Each node should have an 'id' and 'data'.
    :param tweaks: The dictionary containing the tweaks. The keys can be the node id or the name of the tweak.
                   The values can be a dictionary containing the tweaks for the node or the value of the tweak.
    :param stream: A boolean flag indicating whether streaming should be deactivated across all components or not. Default is False.
    :return: The modified graph_data dictionary.
    :raises ValueError: If the input is not in the expected format.
    """
    tweaks_dict = {}
    if not isinstance(tweaks, dict):
        tweaks_dict = tweaks.model_dump()
    else:
        tweaks_dict = tweaks
    if "stream" not in tweaks_dict:
        tweaks_dict["stream"] = stream
    nodes = validate_input(graph_data, tweaks_dict)
    nodes_map = {node.get("id"): node for node in nodes}
    nodes_display_name_map = {node.get("data", {}).get("node", {}).get("display_name"): node for node in nodes}

    all_nodes_tweaks = {}
    for key, value in tweaks_dict.items():
        if isinstance(value, dict):
            if node := nodes_map.get(key):
                apply_tweaks(node, value)
            elif node := nodes_display_name_map.get(key):
                apply_tweaks(node, value)
        else:
            all_nodes_tweaks[key] = value
    if all_nodes_tweaks:
        for node in nodes:
            apply_tweaks(node, all_nodes_tweaks)

    return graph_data


def process_tweaks_on_graph(graph: Graph, tweaks: Dict[str, Dict[str, Any]]):
    for vertex in graph.vertices:
        if isinstance(vertex, Vertex) and isinstance(vertex.id, str):
            node_id = vertex.id
            if node_tweaks := tweaks.get(node_id):
                apply_tweaks_on_vertex(vertex, node_tweaks)
        else:
            logger.warning("Each node should be a Vertex with an 'id' attribute of type str")

    return graph
