from typing import List, Union, TYPE_CHECKING
from langflow.api.v1.callback import (
    AsyncStreamingLLMCallbackHandler,
    StreamingLLMCallbackHandler,
)
from langflow.processing.process import fix_memory_inputs, format_actions
from loguru import logger
from langchain.agents.agent import AgentExecutor
from langchain.callbacks.base import BaseCallbackHandler

if TYPE_CHECKING:
    from langfuse.callback import CallbackHandler  # type: ignore


def setup_callbacks(sync, trace_id, **kwargs):
    """Setup callbacks for langchain object"""
    callbacks = []
    if sync:
        callbacks.append(StreamingLLMCallbackHandler(**kwargs))
    else:
        callbacks.append(AsyncStreamingLLMCallbackHandler(**kwargs))

    if langfuse_callback := get_langfuse_callback(trace_id=trace_id):
        logger.debug("Langfuse callback loaded")
        callbacks.append(langfuse_callback)
    return callbacks


def get_langfuse_callback(trace_id):
    from langflow.services.plugins.langfuse import LangfuseInstance
    from langfuse.callback import CreateTrace

    logger.debug("Initializing langfuse callback")
    if langfuse := LangfuseInstance.get():
        logger.debug("Langfuse credentials found")
        try:
            trace = langfuse.trace(CreateTrace(id=trace_id))
            return trace.getNewHandler()
        except Exception as exc:
            logger.error(f"Error initializing langfuse callback: {exc}")

    return None


def flush_langfuse_callback_if_present(
    callbacks: List[Union[BaseCallbackHandler, "CallbackHandler"]]
):
    """
    If langfuse callback is present, run callback.langfuse.flush()
    """
    for callback in callbacks:
        if hasattr(callback, "langfuse"):
            callback.langfuse.flush()
            break


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
            trace_id = kwargs.pop("session_id", None)
            callbacks = setup_callbacks(sync=False, trace_id=trace_id, **kwargs)
            output = await langchain_object.acall(inputs, callbacks=callbacks)
        except Exception as exc:
            # make the error message more informative
            logger.debug(f"Error: {str(exc)}")
            trace_id = kwargs.pop("session_id", None)
            callbacks = setup_callbacks(sync=True, trace_id=trace_id, **kwargs)
            output = langchain_object(inputs, callbacks=callbacks)

        # if langfuse callback is present, run callback.langfuse.flush()
        flush_langfuse_callback_if_present(callbacks)

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
