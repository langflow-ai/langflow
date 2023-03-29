import contextlib
import io
import re
from typing import Any, Dict

from langflow.interface import loading
from langflow.utils import payload
from langflow.graph.graph import Graph


def process_graph(data_graph: Dict[str, Any]):
    """
    Process graph by extracting input variables and replacing ZeroShotPrompt
    with PromptTemplate,then run the graph and return the result and thought.
    """
    nodes = data_graph["nodes"]
    # Add input variables
    # ? Is this necessary?
    nodes = payload.extract_input_variables(nodes)
    # Nodes, edges and root node
    edges = data_graph["edges"]
    graph = Graph(nodes, edges)

    langchain_object = graph.build()
    message = data_graph["message"]
    # Process json
    result, thought = get_result_and_thought_using_graph(langchain_object, message)

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

    except Exception as e:
        result = f"Error: {str(e)}"
        thought = ""
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
