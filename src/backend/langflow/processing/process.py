import contextlib
import io
from langchain.schema import AgentAction
import json
from langflow.interface.run import (
    build_langchain_object_with_caching,
    get_memory_key,
    update_memory_keys,
)
from langflow.utils.logger import logger
from langflow.graph import Graph


from typing import Any, Dict, List, Tuple


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


def get_result_and_thought(langchain_object, message: str):
    """Get result and thought from extracted json"""
    try:
        if hasattr(langchain_object, "verbose"):
            langchain_object.verbose = True
        chat_input = None
        memory_key = ""
        if hasattr(langchain_object, "memory") and langchain_object.memory is not None:
            memory_key = langchain_object.memory.memory_key

        if hasattr(langchain_object, "input_keys"):
            for key in langchain_object.input_keys:
                if key not in [memory_key, "chat_history"]:
                    chat_input = {key: message}
        else:
            chat_input = message  # type: ignore

        if hasattr(langchain_object, "return_intermediate_steps"):
            # https://github.com/hwchase17/langchain/issues/2068
            # Deactivating until we have a frontend solution
            # to display intermediate steps
            langchain_object.return_intermediate_steps = False

        fix_memory_inputs(langchain_object)

        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            try:
                # if hasattr(langchain_object, "acall"):
                #     output = await langchain_object.acall(chat_input)
                # else:
                output = langchain_object(chat_input)
            except ValueError as exc:
                # make the error message more informative
                logger.debug(f"Error: {str(exc)}")
                output = langchain_object.run(chat_input)

            intermediate_steps = (
                output.get("intermediate_steps", []) if isinstance(output, dict) else []
            )

            result = (
                output.get(langchain_object.output_keys[0])
                if isinstance(output, dict)
                else output
            )
            if intermediate_steps:
                thought = format_actions(intermediate_steps)
            else:
                thought = output_buffer.getvalue()

    except Exception as exc:
        raise ValueError(f"Error: {str(exc)}") from exc
    return result, thought


def load_or_build_langchain_object(data_graph, is_first_message=False):
    """
    Load langchain object from cache if it exists, otherwise build it.
    """
    if is_first_message:
        build_langchain_object_with_caching.clear_cache()
    return build_langchain_object_with_caching(data_graph)


def process_graph_cached(data_graph: Dict[str, Any], message: str):
    """
    Process graph by extracting input variables and replacing ZeroShotPrompt
    with PromptTemplate,then run the graph and return the result and thought.
    """
    # Load langchain object
    is_first_message = len(data_graph.get("chatHistory", [])) == 0
    langchain_object = load_or_build_langchain_object(data_graph, is_first_message)
    logger.debug("Loaded langchain object")

    if langchain_object is None:
        # Raise user facing error
        raise ValueError(
            "There was an error loading the langchain_object. Please, check all the nodes and try again."
        )

    # Generate result and thought
    logger.debug("Generating result and thought")
    result, thought = get_result_and_thought(langchain_object, message)
    logger.debug("Generated result and thought")
    return {"result": str(result), "thought": thought.strip()}


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
