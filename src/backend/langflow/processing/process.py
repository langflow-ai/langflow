import json
from langflow.interface.run import (
    get_memory_key,
    update_memory_keys,
)
from langflow.graph import Graph


def fix_memory_inputs(langchain_object):
    """
    Given a LangChain object, this function checks if it has a memory attribute and if that memory key exists in the
    object's input variables. If so, it does nothing. Otherwise, it gets a possible new memory key using the
    get_memory_key function and updates the memory keys using the update_memory_keys function.
    """
    if hasattr(langchain_object, "memory") and langchain_object.memory is not None:
        try:
            if langchain_object.memory.memory_key in langchain_object.input_variables:
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


def load_flow_from_json(path: str, build=True):
    """Load flow from json file"""
    # This is done to avoid circular imports

    with open(path, "r", encoding="utf-8") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    # Substitute ZeroShotPrompt with PromptTemplate
    # nodes = replace_zero_shot_prompt_with_prompt_template(nodes)
    # Add input variables
    # nodes = payload.extract_input_variables(nodes)

    # Nodes, edges and root node
    edges = data_graph["edges"]
    graph = Graph(nodes, edges)
    if build:
        langchain_object = graph.build()
        if hasattr(langchain_object, "verbose"):
            langchain_object.verbose = True

        if hasattr(langchain_object, "return_intermediate_steps"):
            # https://github.com/hwchase17/langchain/issues/2068
            # Deactivating until we have a frontend solution
            # to display intermediate steps
            langchain_object.return_intermediate_steps = False
        fix_memory_inputs(langchain_object)
        return langchain_object
    return graph
