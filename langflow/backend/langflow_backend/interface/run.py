import contextlib
import io
import re
from typing import Any, Dict
from langflow_backend.interface.loading import (
    load_langchain_type_from_config,
    replace_zero_shot_prompt_with_prompt_template,
)
from langflow_backend.utils import payload


def process_data_graph(data_graph: Dict[str, Any]):
    """
    Process data graph by extracting input variables and replacing ZeroShotPrompt
    with PromptTemplate,then run the graph and return the result and thought.
    """
    nodes = data_graph["nodes"]
    # Substitute ZeroShotPrompt with PromptTemplate
    nodes = replace_zero_shot_prompt_with_prompt_template(nodes)
    # Add input variables
    data_graph = payload.extract_input_variables(data_graph)
    # Nodes, edges and root node
    message = data_graph["message"]
    edges = data_graph["edges"]
    root = payload.get_root_node(data_graph)
    extracted_json = payload.build_json(root, nodes, edges)

    # Process json
    result, thought = get_result_and_thought(extracted_json, message)

    # Remove unnecessary data from response
    begin = thought.rfind(message)
    thought = thought[(begin + len(message)) :]

    return {
        "result": result,
        "thought": re.sub(
            r"\x1b\[([0-9,A-Z]{1,2}(;[0-9,A-Z]{1,2})?)?[m|K]", "", thought
        ).strip(),
    }


def get_result_and_thought(extracted_json: Dict[str, Any], message: str):
    """Get result and thought from extracted json"""
    # Get type list
    try:
        loaded = load_langchain_type_from_config(config=extracted_json)
        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            result = loaded(message)
            thought = output_buffer.getvalue()
    except Exception as e:
        result = f"Error: {str(e)}"
        thought = ""
    return result, thought
