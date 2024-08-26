from typing import List, Optional

import sqlalchemy as sa

from langflow.api.v1.schemas import InputValueRequest, RunResponse, SimplifiedAPIRequest
from langflow.exceptions.api import InvalidChatInputException
from langflow.graph.graph.base import Graph
from langflow.graph.schema import RunOutputs
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.user.model import User


def validate_input_and_tweaks(input_request: SimplifiedAPIRequest):
    # If the input_value is not None and the input_type is "chat"
    # then we need to check the tweaks if the ChatInput component is present
    # and if its input_value is not None
    # if so, we raise an error
    if input_request.tweaks is None:
        return
    for key, value in input_request.tweaks.items():
        if "ChatInput" in key or "Chat Input" in key:
            if isinstance(value, dict):
                has_input_value = value.get("input_value") is not None
                input_value_is_chat = input_request.input_value is not None and input_request.input_type == "chat"
                if has_input_value and input_value_is_chat:
                    raise InvalidChatInputException(
                        "If you pass an input_value to the chat input, you cannot pass a tweak with the same name."
                    )
        elif "Text Input" in key or "TextInput" in key:
            if isinstance(value, dict):
                has_input_value = value.get("input_value") is not None
                input_value_is_text = input_request.input_value is not None and input_request.input_type == "text"
                if has_input_value and input_value_is_text:
                    raise InvalidChatInputException(
                        "If you pass an input_value to the text input, you cannot pass a tweak with the same name."
                    )


async def simple_run_flow(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    stream: bool = False,
    api_key_user: Optional[User] = None,
):
    if input_request.input_value is not None and input_request.tweaks is not None:
        validate_input_and_tweaks(input_request)
    try:
        task_result: List[RunOutputs] = []
        user_id = api_key_user.id if api_key_user else None
        flow_id_str = str(flow.id)
        if flow.data is None:
            raise ValueError(f"Flow {flow_id_str} has no data")
        graph_data = flow.data.copy()
        graph_data = process_tweaks(graph_data, input_request.tweaks or {}, stream=stream)
        graph = Graph.from_payload(graph_data, flow_id=flow_id_str, user_id=str(user_id), flow_name=flow.name)
        inputs = [
            InputValueRequest(components=[], input_value=input_request.input_value, type=input_request.input_type)
        ]
        if input_request.output_component:
            outputs = [input_request.output_component]
        else:
            outputs = [
                vertex.id
                for vertex in graph.vertices
                if input_request.output_type == "debug"
                or (
                    vertex.is_output
                    and (input_request.output_type == "any" or input_request.output_type in vertex.id.lower())  # type: ignore
                )
            ]
        task_result, session_id = await run_graph_internal(
            graph=graph,
            flow_id=flow_id_str,
            session_id=input_request.session_id,
            inputs=inputs,
            outputs=outputs,
            stream=stream,
        )

        return RunResponse(outputs=task_result, session_id=session_id)

    except sa.exc.StatementError as exc:
        raise ValueError(str(exc)) from exc
