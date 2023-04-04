import contextlib
import io
from typing import Any, Dict

from langflow.cache.utils import compute_hash, load_cache, save_cache
from langflow.graph.graph import Graph
from langflow.interface import loading
from langflow.utils.logger import logger


def load_langchain_object(data_graph, is_first_message=False):
    """
    Load langchain object from cache if it exists, otherwise build it.
    """
    computed_hash = compute_hash(data_graph)
    if is_first_message:
        langchain_object = build_langchain_object(data_graph)
    else:
        logger.debug("Loading langchain object from cache")
        langchain_object = load_cache(computed_hash)

    return computed_hash, langchain_object


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


def process_graph(data_graph: Dict[str, Any]):
    """
    Process graph by extracting input variables and replacing ZeroShotPrompt
    with PromptTemplate,then run the graph and return the result and thought.
    """
    # Load langchain object
    logger.debug("Loading langchain object")
    message = data_graph.pop("message", "")
    is_first_message = len(data_graph.get("chatHistory", [])) == 0
    computed_hash, langchain_object = load_langchain_object(
        data_graph, is_first_message
    )
    logger.debug("Loaded langchain object")

    if langchain_object is None:
        # Raise user facing error
        raise ValueError(
            "There was an error loading the langchain_object. Please, check all the nodes and try again."
        )

    # Generate result and thought
    logger.debug("Generating result and thought")
    result, thought = get_result_and_thought_using_graph(langchain_object, message)
    logger.debug("Generated result and thought")

    # Save langchain_object to cache
    # We have to save it here because if the
    # memory is updated we need to keep the new values
    logger.debug("Saving langchain object to cache")
    save_cache(computed_hash, langchain_object, is_first_message)
    logger.debug("Saved langchain object to cache")
    return {"result": str(result), "thought": thought.strip()}


def fix_memory_inputs_for_intermediate_steps(langchain_object):
    """
    Fix memory inputs by replacing the memory key with the input key.
    """
    langchain_object.return_intermediate_steps = True
    langchain_object.memory.memory_key
    input_key = [
        key
        for key in langchain_object.input_keys
        if key != langchain_object.memory.memory_key
    ][0]
    # get output_key
    output_key = [
        key
        for key in langchain_object.output_keys
        if key != langchain_object.memory.memory_key
    ][0]
    # set input_key and output_key in memory
    langchain_object.memory.input_key = input_key
    langchain_object.memory.output_key = output_key


def get_result_and_thought_using_graph(langchain_object, message: str):
    """Get result and thought from extracted json"""
    try:
        if hasattr(langchain_object, "verbose"):
            langchain_object.verbose = True
        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            chat_input = None
            memory_key = ""
            if (
                hasattr(langchain_object, "memory")
                and langchain_object.memory is not None
            ):
                memory_key = langchain_object.memory.memory_key

            for key in langchain_object.input_keys:
                if key not in [memory_key, "chat_history"]:
                    chat_input = {key: message}

            if hasattr(langchain_object, "return_intermediate_steps"):
                # https://github.com/hwchase17/langchain/issues/2068
                # Deactivating until we have a frontend solution
                # to display intermediate steps
                langchain_object.return_intermediate_steps = False
                if langchain_object.return_intermediate_steps:
                    fix_memory_inputs_for_intermediate_steps(langchain_object)

            try:
                output = langchain_object(chat_input)
            except ValueError as exc:
                # make the error message more informative
                logger.debug(f"Error: {str(exc)}")
                if hasattr(langchain_object, "memory"):
                    langchain_object.memory.memory_key = memory_key
                output = langchain_object(chat_input)

            intermediate_steps = (
                output.get("intermediate_steps", []) if isinstance(output, dict) else []
            )

            result = (
                output.get(langchain_object.output_keys[0])
                if isinstance(output, dict)
                else output
            )
            if intermediate_steps:
                thought = format_intermediate_steps(intermediate_steps)
            else:
                thought = output_buffer.getvalue()

    except Exception as exc:
        raise ValueError(f"Error: {str(exc)}") from exc
    return result, thought


def get_result_and_thought(extracted_json: Dict[str, Any], message: str):
    """Get result and thought from extracted json"""
    try:
        langchain_object = loading.load_langchain_type_from_config(
            config=extracted_json
        )
        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            output = langchain_object(message)
            intermediate_steps = (
                output.get("intermediate_steps", []) if isinstance(output, dict) else []
            )
            result = (
                output.get(langchain_object.output_keys[0])
                if isinstance(output, dict)
                else output
            )

            if intermediate_steps:
                thought = format_intermediate_steps(intermediate_steps)
            else:
                thought = output_buffer.getvalue()

    except Exception as e:
        result = f"Error: {str(e)}"
        thought = ""
    return result, thought


def format_intermediate_steps(intermediate_steps):
    formatted_chain = "> Entering new AgentExecutor chain...\n"
    for step in intermediate_steps:
        action = step[0]
        observation = step[1]

        formatted_chain += (
            f" {action.log}\nAction: {action.tool}\nAction Input: {action.tool_input}\n"
        )
        formatted_chain += f"Observation: {observation}\n"

    final_answer = f"Final Answer: {observation}\n"
    formatted_chain += f"Thought: I now know the final answer\n{final_answer}\n"
    formatted_chain += "> Finished chain.\n"

    return formatted_chain
