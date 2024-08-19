from typing import TYPE_CHECKING, List, Union

from langchain_core.callbacks import BaseCallbackHandler
from loguru import logger

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
