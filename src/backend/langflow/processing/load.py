import asyncio
import json
from pathlib import Path
from typing import Optional, Union

from langflow.graph import Graph
from langflow.processing.process import fix_memory_inputs, process_tweaks


def load_flow_from_json(flow: Union[Path, str, dict], tweaks: Optional[dict] = None, build=True):
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
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]
    graph = Graph(nodes, edges)

    if build:
        langchain_object = asyncio.run(graph.build())

        if hasattr(langchain_object, "verbose"):
            langchain_object.verbose = True

        if hasattr(langchain_object, "return_intermediate_steps"):
            # Deactivating until we have a frontend solution
            # to display intermediate steps
            langchain_object.return_intermediate_steps = False

        fix_memory_inputs(langchain_object)
        return langchain_object

    return graph

    return graph
