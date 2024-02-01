from typing import Any, Optional, Union

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langflow.services.deps import get_socket_service
from langflow.utils.constants import PYTHON_BASIC_TYPES


def is_basic_type(obj):
    return type(obj) in PYTHON_BASIC_TYPES


async def invoke_lc_runnable(
    built_object: Runnable, inputs: dict, has_external_output: bool, session_id: Optional[str] = None
) -> Union[str, BaseMessage]:
    if has_external_output:
        socketio_service = get_socket_service()
        result = ""
        stream = built_object.astream(inputs)
        async for chunk in stream:
            await socketio_service.emit_token(session_id, chunk)
            result += chunk
    return await built_object.ainvoke(inputs)


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
