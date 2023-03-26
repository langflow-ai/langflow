import contextlib
import io
import re
from typing import Any, Dict

from langflow.interface import loading


def process_data_graph(data_graph: Dict[str, Any]):
    """
    Process data graph by extracting input variables and replacing ZeroShotPrompt
    with PromptTemplate,then run the graph and return the result and thought.
    """

    extracted_json = loading.extract_json(data_graph)

    message = data_graph["message"]

    # Process json
    result, thought = get_result_and_thought(extracted_json, message)

    return {
        "result": result,
        "thought": re.sub(
            r"\x1b\[([0-9,A-Z]{1,2}(;[0-9,A-Z]{1,2})?)?[m|K]", "", thought
        ).strip(),
    }


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
