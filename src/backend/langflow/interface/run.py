import contextlib
import io
import re
from typing import Any, Dict

from langflow.cache.utils import compute_hash, load_cache, save_cache
from langflow.graph.graph import Graph
from langflow.interface import loading
from langflow.utils import payload


def load_langchain_object(data_graph):
    computed_hash = compute_hash(data_graph)

    # Load langchain_object from cache if it exists
    langchain_object = load_cache(computed_hash)
    if langchain_object is None:
        nodes = data_graph["nodes"]
        # Add input variables
        nodes = payload.extract_input_variables(nodes)
        # Nodes, edges and root node
        edges = data_graph["edges"]
        graph = Graph(nodes, edges)

        langchain_object = graph.build()

    return computed_hash, langchain_object


def process_graph(data_graph: Dict[str, Any]):
    """
    Process graph by extracting input variables and replacing ZeroShotPrompt
    with PromptTemplate,then run the graph and return the result and thought.
    """
    # Load langchain object
    computed_hash, langchain_object = load_langchain_object(data_graph)
    message = data_graph["message"]

    # Generate result and thought
    result, thought = get_result_and_thought_using_graph(langchain_object, message)

    # Save langchain_object to cache
    # We have to save it here because if the
    # memory is updated we need to keep the new values
    save_cache(computed_hash, langchain_object)

    return {
        "result": result,
        "thought": re.sub(
            r"\x1b\[([0-9,A-Z]{1,2}(;[0-9,A-Z]{1,2})?)?[m|K]", "", thought
        ).strip(),
    }


def get_result_and_thought_using_graph(loaded_langchain, message: str):
    """Get result and thought from extracted json"""
    loaded_langchain.verbose = True
    try:
        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            result = loaded_langchain(message)

            result = (
                result.get(loaded_langchain.output_keys[0])
                if isinstance(result, dict)
                else result
            )
            thought = output_buffer.getvalue()

    except Exception as exc:
        raise ValueError(f"Error: {str(exc)}") from exc
    return result, thought


def get_result_and_thought(extracted_json: Dict[str, Any], message: str):
    """Get result and thought from extracted json"""
    try:
        loaded_langchain = loading.load_langchain_type_from_config(
            config=extracted_json
        )
        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            result = loaded_langchain(message)
            result = (
                result.get(loaded_langchain.output_keys[0])
                if isinstance(result, dict)
                else result
            )
            thought = output_buffer.getvalue()

    except Exception as e:
        result = f"Error: {str(e)}"
        thought = ""
    return result, thought
