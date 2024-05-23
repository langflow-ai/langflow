from typing import Any, Optional, Union, TYPE_CHECKING

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from loguru import logger

from langflow.services.deps import get_monitor_service
from langflow.utils.constants import PYTHON_BASIC_TYPES

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


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


def build_clean_params(target: "Vertex") -> dict:
    """
    Cleans the parameters of the target vertex.
    """
    # Removes all keys that the values aren't python types like str, int, bool, etc.
    params = {
        key: value for key, value in target.params.items() if isinstance(value, (str, int, bool, float, list, dict))
    }
    # if it is a list we need to check if the contents are python types
    for key, value in params.items():
        if isinstance(value, list):
            params[key] = [item for item in value if isinstance(item, (str, int, bool, float, list, dict))]
    return params


def log_transaction(source: "Vertex", target: "Vertex", flow_id, status, error=None):
    """
    Logs a transaction between two vertices.

    Args:
        source (Vertex): The source vertex of the transaction.
        target (Vertex): The target vertex of the transaction.
        status: The status of the transaction.
        error (Optional): Any error associated with the transaction.

    Raises:
        Exception: If there is an error while logging the transaction.

    """
    try:
        monitor_service = get_monitor_service()
        clean_params = build_clean_params(target)
        data = {
            "source": source.vertex_type,
            "target": target.vertex_type,
            "target_args": clean_params,
            "timestamp": monitor_service.get_timestamp(),
            "status": status,
            "error": error,
            "flow_id": flow_id,
        }
        monitor_service.add_row(table_name="transactions", data=data)
    except Exception as e:
        logger.error(f"Error logging transaction: {e}")
