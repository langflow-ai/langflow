from langflow.cache.utils import memoize_dict
from langflow.graph import Graph
from langflow.utils.logger import logger


@memoize_dict(maxsize=10)
def build_langchain_object_with_caching(data_graph):
    """
    Build langchain object from data_graph.
    """

    logger.debug("Building langchain object")
    graph = Graph.from_payload(data_graph)
    return graph.build()


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
    memory_key = langchain_object.memory.memory_key
    return mem_key_dict.get(memory_key)


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

    langchain_object.memory.input_key = input_key
    langchain_object.memory.output_key = output_key
    langchain_object.memory.memory_key = possible_new_mem_key
