from typing import Union
from langflow.api.v1.callback import (
    AsyncStreamingLLMCallbackHandler,
    StreamingLLMCallbackHandler,
)
from langflow.processing.process import fix_memory_inputs, format_actions
from langflow.utils.logger import logger
from langchain.agents.agent import AgentExecutor


def setup_callbacks(sync, **kwargs):
    """Setup callbacks for langchain object"""
    callbacks = []
    if sync:
        callbacks.append(StreamingLLMCallbackHandler(**kwargs))
    else:
        callbacks.append(AsyncStreamingLLMCallbackHandler(**kwargs))

    if langfuse_callback := get_langfuse_callback():
        callbacks.append(langfuse_callback)
    return callbacks


def get_langfuse_callback():
    from langflow.settings import settings

    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        try:
            from langfuse.callback import CallbackHandler

            return CallbackHandler(
                settings.LANGFUSE_PUBLIC_KEY, settings.LANGFUSE_SECRET_KEY
            )
        except Exception as exc:
            logger.error(f"Error initializing langfuse callback: {exc}")
    return None


async def get_result_and_steps(langchain_object, inputs: Union[dict, str], **kwargs):
    """Get result and thought from extracted json"""

    try:
        if hasattr(langchain_object, "verbose"):
            langchain_object.verbose = True

        if hasattr(langchain_object, "return_intermediate_steps"):
            # https://github.com/hwchase17/langchain/issues/2068
            # Deactivating until we have a frontend solution
            # to display intermediate steps
            langchain_object.return_intermediate_steps = True
        try:
            if not isinstance(langchain_object, AgentExecutor):
                fix_memory_inputs(langchain_object)
        except Exception as exc:
            logger.error(f"Error fixing memory inputs: {exc}")

        try:
            async_callbacks = setup_callbacks(sync=False, **kwargs)
            output = await langchain_object.acall(inputs, callbacks=async_callbacks)
        except Exception as exc:
            # make the error message more informative
            logger.debug(f"Error: {str(exc)}")
            sync_callbacks = setup_callbacks(sync=True, **kwargs)
            output = langchain_object(inputs, callbacks=sync_callbacks)

        intermediate_steps = (
            output.get("intermediate_steps", []) if isinstance(output, dict) else []
        )

        result = (
            output.get(langchain_object.output_keys[0])
            if isinstance(output, dict)
            else output
        )
        try:
            thought = format_actions(intermediate_steps) if intermediate_steps else ""
        except Exception as exc:
            logger.exception(exc)
            thought = ""
    except Exception as exc:
        logger.exception(exc)
        raise ValueError(f"Error: {str(exc)}") from exc
    return result, thought
