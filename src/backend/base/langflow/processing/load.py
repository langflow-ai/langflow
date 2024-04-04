import json
from pathlib import Path
from typing import List, Optional, Union

from langflow.graph import Graph
from langflow.graph.schema import RunOutputs
from langflow.processing.process import process_tweaks, run_graph


def load_flow_from_json(flow: Union[Path, str, dict], tweaks: Optional[dict] = None) -> Graph:
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
        raise TypeError("Input must be either a file path (str) or a JSON object (dict)")

    graph_data = flow_graph["data"]
    if tweaks is not None:
        graph_data = process_tweaks(graph_data, tweaks)

    graph = Graph.from_payload(graph_data)
    return graph


def run_flow_from_json(
    flow: Union[Path, str, dict],
    input_value: str,
    tweaks: Optional[dict] = None,
    input_type: str = "chat",
    output_type: str = "chat",
    output_component: Optional[str] = None,
) -> List[RunOutputs]:
    """
    Runs a JSON flow by loading it from a file or dictionary and executing it with the given input value.

    Args:
        flow (Union[Path, str, dict]): The path to the JSON file, or the JSON dictionary representing the flow.
        input_value (str): The input value to be processed by the flow.
        tweaks (Optional[dict], optional): Optional tweaks to be applied to the flow. Defaults to None.
        input_type (str, optional): The type of the input value. Defaults to "chat".
        output_type (str, optional): The type of the output value. Defaults to "chat".
        output_component (Optional[str], optional): The specific output component to retrieve. Defaults to None.

    Returns:
        None: The result of running the flow.
    """
    graph = load_flow_from_json(flow, tweaks)
    result = run_graph(
        graph=graph,
        input_value=input_value,
        input_type=input_type,
        output_type=output_type,
        output_component=output_component,
    )
    return result
