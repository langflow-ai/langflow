from typing import TYPE_CHECKING, List, Union

from langchain.agents.agent import AgentExecutor
from langchain.callbacks.base import BaseCallbackHandler
from loguru import logger

from langflow.processing.process import fix_memory_inputs, format_actions
from langflow.services.deps import get_plugins_service

if TYPE_CHECKING:
    from langfuse.callback import CallbackHandler  # type: ignore


def setup_callbacks(sync, trace_id, **kwargs):
    """Setup callbacks for langchain object"""
    callbacks = []
    plugin_service = get_plugins_service()
    plugin_callbacks = plugin_service.get_callbacks(_id=trace_id)
    if plugin_callbacks:
        callbacks.extend(plugin_callbacks)
    return callbacks


def get_langfuse_callback(trace_id):
    from langflow.services.deps import get_plugins_service

    logger.debug("Initializing langfuse callback")
    if langfuse := get_plugins_service().get("langfuse"):
        logger.debug("Langfuse credentials found")
        try:
            trace = langfuse.trace(name="langflow-" + trace_id, id=trace_id)
            return trace.getNewHandler()
        except Exception as exc:
            logger.error(f"Error initializing langfuse callback: {exc}")

    return None


def flush_langfuse_callback_if_present(callbacks: List[Union[BaseCallbackHandler, "CallbackHandler"]]):
    """
    If langfuse callback is present, run callback.langfuse.flush()
    """
    for callback in callbacks:
        if hasattr(callback, "langfuse") and hasattr(callback.langfuse, "flush"):
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

        trace_id = kwargs.pop("session_id", None)
        try:
            callbacks = setup_callbacks(sync=False, trace_id=trace_id, **kwargs)
            output = await langchain_object.acall(inputs, callbacks=callbacks)
        except Exception as exc:
            # make the error message more informative
            logger.debug(f"Error: {str(exc)}")
            callbacks = setup_callbacks(sync=True, trace_id=trace_id, **kwargs)
            output = langchain_object(inputs, callbacks=callbacks)

        # if langfuse callback is present, run callback.langfuse.flush()
        flush_langfuse_callback_if_present(callbacks)

        intermediate_steps = output.get("intermediate_steps", []) if isinstance(output, dict) else []

        result = output.get(langchain_object.output_keys[0]) if isinstance(output, dict) else output
        try:
            thought = format_actions(intermediate_steps) if intermediate_steps else ""
        except Exception as exc:
            logger.exception(exc)
            thought = ""
    except Exception as exc:
        logger.exception(exc)
        raise ValueError(f"Error: {str(exc)}") from exc
    return result, thought, output
