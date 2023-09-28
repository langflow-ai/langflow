from typing import Dict, Tuple
from langflow.graph import Graph
from loguru import logger


def build_sorted_vertices(data_graph) -> Tuple[Graph, Dict]:
    """
    Build langchain object from data_graph.
    """

    logger.debug("Building langchain object")
    graph = Graph.from_payload(data_graph)
    sorted_vertices = graph.topological_sort()
    artifacts = {}
    for vertex in sorted_vertices:
        vertex.build()
        if vertex.artifacts:
            artifacts.update(vertex.artifacts)
    return graph, artifacts


def build_langchain_object(data_graph):
    """
    Build langchain object from data_graph.
    """

    logger.debug("Building langchain object")
    nodes = data_graph["nodes"]
    # Add input variables
    # nodes = payload.extract_input_variables(nodes)
    # Nodes, edges and root node
    edges = data_graph["edges"]
    graph = Graph(nodes, edges)

    return graph.build()


def get_memory_key(langchain_object):
    """
    Given a LangChain object, this function retrieves the current memory key from the object's memory attribute.
    It then checks if the key exists in a dictionary of known memory keys and returns the corresponding key,
    or None if the current key is not recognized.
    """
    mem_key_dict = {
        "chat_history": "history",
        "history": "chat_history",
    }
    # Check if memory_key attribute exists
    if hasattr(langchain_object.memory, "memory_key"):
        memory_key = langchain_object.memory.memory_key
        return mem_key_dict.get(memory_key)
    else:
        return None  # or some other default value or action


def update_memory_keys(langchain_object, possible_new_mem_key):
    """
    Given a LangChain object and a possible new memory key, this function updates the input and output keys in the
    object's memory attribute to exclude the current memory key and the possible new key. It then sets the memory key
    to the possible new key.
    """
    input_key = [
        key
        for key in langchain_object.input_keys
        if key not in [langchain_object.memory.memory_key, possible_new_mem_key]
    ][0]

    output_key = [
        key
        for key in langchain_object.output_keys
        if key not in [langchain_object.memory.memory_key, possible_new_mem_key]
    ][0]

    keys = [input_key, output_key, possible_new_mem_key]
    attrs = ["input_key", "output_key", "memory_key"]
    for key, attr in zip(keys, attrs):
        try:
            setattr(langchain_object.memory, attr, key)
        except ValueError as exc:
            logger.debug(f"{langchain_object.memory} has no attribute {attr} ({exc})")
