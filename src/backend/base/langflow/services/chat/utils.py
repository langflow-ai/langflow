from typing import Any

from langchain.agents import AgentExecutor
from langchain.chains.base import Chain
from langchain_core.runnables import Runnable
from loguru import logger

from langflow.api.v1.schemas import ChatMessage
from langflow.interface.utils import try_setting_streaming_options
from langflow.processing.base import get_result_and_steps

LANGCHAIN_RUNNABLES = (Chain, Runnable, AgentExecutor)


async def process_graph(
    build_result,
    chat_inputs: ChatMessage,
    client_id: str,
    session_id: str,
):
    build_result = try_setting_streaming_options(build_result)
    logger.debug("Loaded langchain object")

    if build_result is None:
        # Raise user facing error
        raise ValueError("There was an error loading the langchain_object. Please, check all the nodes and try again.")

    # Generate result and thought
    try:
        if chat_inputs.message is None:
            logger.debug("No message provided")
            chat_inputs.message = {}

        logger.debug("Generating result and thought")
        if isinstance(build_result, LANGCHAIN_RUNNABLES):
            result, intermediate_steps, raw_output = await get_result_and_steps(
                build_result,
                chat_inputs.message,
                client_id=client_id,
                session_id=session_id,
            )
        else:
            raise TypeError(f"Unknown type {type(build_result)}")
        logger.debug("Generated result and intermediate_steps")
        return result, intermediate_steps, raw_output
    except Exception as e:
        # Log stack trace
        logger.exception(e)
        raise e


async def run_build_result(build_result: Any, chat_inputs: ChatMessage, client_id: str, session_id: str):
    return build_result(inputs=chat_inputs.message)
