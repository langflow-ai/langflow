import contextlib
import io
from typing import List, Tuple

from langflow.utils.logger import logger
from langchain.schema import AgentAction


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


def fix_memory_inputs(langchain_object):
    """
    Given a LangChain object, this function checks if it has a memory attribute and if that memory key exists in the
    object's input variables. If so, it does nothing. Otherwise, it gets a possible new memory key using the
    get_memory_key function and updates the memory keys using the update_memory_keys function.
    """
    if not hasattr(langchain_object, "memory") or langchain_object.memory is None:
        return
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


def format_actions(actions: List[Tuple[AgentAction, str]]) -> str:
    """Format a list of (AgentAction, answer) tuples into a string."""
    output = []
    for action, answer in actions:
        log = action.log
        output.append(f"Log: {log}")
        if "Action" not in log and "Action Input" not in log:
            tool = action.tool
            tool_input = action.tool_input
            output.extend((f"Tool: {tool}", f"Tool Input: {tool_input}"))
        output.extend((f"Answer: {answer}", ""))
    return "\n".join(output)
