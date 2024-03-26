from typing import Any, Optional, Union

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from loguru import logger

from langflow.utils.constants import PYTHON_BASIC_TYPES


def is_basic_type(obj):
    return type(obj) in PYTHON_BASIC_TYPES


async def invoke_lc_runnable(
    built_object: Runnable, inputs: dict, has_external_output: bool, session_id: Optional[str] = None, **kwargs
) -> Union[str, BaseMessage]:
    # Setup callbacks for asynchronous execution
    from langflow.processing.base import setup_callbacks

    callbacks = setup_callbacks(sync=False, trace_id=session_id, **kwargs)

    try:
        if has_external_output and hasattr(built_object, "astream"):
            # Asynchronous stream handling if supported and required
            output = ""
            async for chunk in built_object.astream(inputs, {"callbacks": callbacks}):
                output += chunk
            return output
        else:
            # Direct asynchronous invocation
            return await built_object.ainvoke(inputs, {"callbacks": callbacks})
    except Exception as async_exc:
        logger.debug(f"Async error, falling back to sync: {str(async_exc)}")

        # Setup synchronous callbacks for the fallback
        sync_callbacks = setup_callbacks(sync=True, trace_id=session_id, **kwargs)
        try:
            # Synchronous fallback if asynchronous execution fails
            if has_external_output and hasattr(built_object, "stream"):
                # Synchronous stream handling if supported and required
                output = ""
                for chunk in built_object.stream(inputs, {"callbacks": sync_callbacks}):
                    output += chunk
                return output
            else:
                # Direct synchronous invocation
                return built_object.invoke(inputs, {"callbacks": sync_callbacks})
        except Exception as sync_exc:
            logger.error(f"Sync error after async failure: {str(sync_exc)}")
            # Handle or re-raise exception as appropriate for your application
            raise sync_exc from async_exc


async def generate_result(built_object: Any, inputs: dict, has_external_output: bool, session_id: Optional[str] = None):
    # If the built_object is instance of Runnable
    # we can call `invoke` or `stream` on it
    # if it has_external_outputl, we need to call `stream` if it has it
    # if not, we call `invoke` if it has it
    if isinstance(built_object, Runnable):
        result = await invoke_lc_runnable(
            built_object=built_object, inputs=inputs, has_external_output=has_external_output, session_id=session_id
        )
    else:
        result = built_object
    return result
