from fastapi import WebSocket
from langflow.api.v1.schemas import ChatMessage
from langflow.processing.process import (
    load_or_build_langchain_object,
)
from langflow.processing.base import get_result_and_steps
from langflow.interface.utils import try_setting_streaming_options
from langflow.utils.logger import logger


from typing import Dict


async def process_graph(
    graph_data: Dict,
    is_first_message: bool,
    chat_message: ChatMessage,
    websocket: WebSocket,
):
    langchain_object = load_or_build_langchain_object(graph_data, is_first_message)
    langchain_object = try_setting_streaming_options(langchain_object, websocket)
    logger.debug("Loaded langchain object")

    if langchain_object is None:
        # Raise user facing error
        raise ValueError(
            "There was an error loading the langchain_object. Please, check all the nodes and try again."
        )

    # Generate result and thought
    try:
        logger.debug("Generating result and thought")
        result, intermediate_steps = await get_result_and_steps(
            langchain_object, chat_message.message or "", websocket=websocket
        )
        logger.debug("Generated result and intermediate_steps")
        return result, intermediate_steps
    except Exception as e:
        # Log stack trace
        logger.exception(e)
        raise e
