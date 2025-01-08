import asyncio
import re
import time
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger

from langflow.api.v1.schemas import InputValueRequest, RunResponse, SimplifiedAPIRequest
from langflow.events.event_manager import EventManager, create_stream_tokens_event_manager
from langflow.exceptions.api import APIException, InvalidChatInputError
from langflow.graph.graph.base import Graph
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_storage_service, get_telemetry_service
from langflow.services.telemetry.schema import RunPayload

if TYPE_CHECKING:
    from langflow.graph.schema import RunOutputs

# Pattern for file name validation
FILE_NAME_PATTERN = re.compile(r"^([^:]+)::([^:]+)::(.+)$")


async def simple_run_flow(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    stream: bool = False,
    api_key_user: User | None = None,
    event_manager: EventManager | None = None,
):
    if input_request.input_value is not None and input_request.tweaks is not None:
        validate_input_and_tweaks(input_request)
    try:
        task_result: list[RunOutputs] = []
        user_id = api_key_user.id if api_key_user else None
        flow_id_str = str(flow.id)
        if flow.data is None:
            msg = f"Flow {flow_id_str} has no data"
            raise ValueError(msg)
        graph_data = flow.data.copy()
        graph_data = process_tweaks(graph_data, input_request.tweaks or {}, stream=stream)
        graph = Graph.from_payload(graph_data, flow_id=flow_id_str, user_id=str(user_id), flow_name=flow.name)
        inputs = [
            InputValueRequest(
                components=[],
                input_value=input_request.input_value,
                type=input_request.input_type,
            )
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
                    and (input_request.output_type == "any" or input_request.output_type in vertex.id.lower())  # type: ignore[operator]
                )
            ]
        task_result, session_id = await run_graph_internal(
            graph=graph,
            flow_id=flow_id_str,
            session_id=input_request.session_id,
            inputs=inputs,
            outputs=outputs,
            stream=stream,
            event_manager=event_manager,
        )

        return RunResponse(outputs=task_result, session_id=session_id)

    except sa.exc.StatementError as exc:
        raise ValueError(str(exc)) from exc


def validate_input_and_tweaks(input_request: SimplifiedAPIRequest) -> None:
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
                    msg = "If you pass an input_value to the chat input, you cannot pass a tweak with the same name."
                    raise InvalidChatInputError(msg)
        elif ("Text Input" in key or "TextInput" in key) and isinstance(value, dict):
            has_input_value = value.get("input_value") is not None
            input_value_is_text = input_request.input_value is not None and input_request.input_type == "text"
            if has_input_value and input_value_is_text:
                msg = "If you pass an input_value to the text input, you cannot pass a tweak with the same name."
                raise InvalidChatInputError(msg)


async def consume_and_yield(queue: asyncio.Queue, client_consumed_queue: asyncio.Queue) -> AsyncGenerator:
    """Consumes events from a queue and yields them to the client while tracking timing metrics.

    This coroutine continuously pulls events from the input queue and yields them to the client.
    It tracks timing metrics for how long events spend in the queue and how long the client takes
    to process them.

    Args:
        queue (asyncio.Queue): The queue containing events to be consumed and yielded
        client_consumed_queue (asyncio.Queue): A queue for tracking when the client has consumed events

    Yields:
        The value from each event in the queue

    Notes:
        - Events are tuples of (event_id, value, put_time)
        - Breaks the loop when receiving a None value, signaling completion
        - Tracks and logs timing metrics for queue time and client processing time
        - Notifies client consumption via client_consumed_queue
    """
    while True:
        event_id, value, put_time = await queue.get()
        if value is None:
            break
        get_time = time.time()
        yield value
        get_time_yield = time.time()
        client_consumed_queue.put_nowait(event_id)
        logger.debug(
            f"consumed event {event_id} "
            f"(time in queue, {get_time - put_time:.4f}, "
            f"client {get_time_yield - get_time:.4f})"
        )


async def run_flow_generator(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    api_key_user: User | None,
    event_manager: EventManager,
    client_consumed_queue: asyncio.Queue,
) -> None:
    """Executes a flow asynchronously and manages event streaming to the client."""
    try:
        result = await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=True,
            api_key_user=api_key_user,
            event_manager=event_manager,
        )
        event_manager.on_end(data={"result": result.model_dump()})
        await client_consumed_queue.get()
    except (ValueError, InvalidChatInputError) as e:
        logger.error(f"Error running flow: {e}")
        event_manager.on_error(data={"error": str(e)})
    finally:
        await event_manager.queue.put((None, None, time.time))


async def log_telemetry(
    background_tasks: BackgroundTasks,
    telemetry_service,
    start_time: float,
    *,
    success: bool,
    error_message: str = "",
    is_webhook: bool = False,
) -> None:
    """Log telemetry data for flow execution."""
    background_tasks.add_task(
        telemetry_service.log_package_run,
        RunPayload(
            run_is_webhook=is_webhook,
            run_seconds=int(time.perf_counter() - start_time),
            run_success=success,
            run_error_message=error_message,
        ),
    )


async def setup_streaming_response(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    api_key_user: User,
    client_consumed_queue: asyncio.Queue,
) -> StreamingResponse:
    """Set up streaming response for flow execution."""
    asyncio_queue: asyncio.Queue = asyncio.Queue()
    event_manager = create_stream_tokens_event_manager(queue=asyncio_queue)
    main_task = asyncio.create_task(
        run_flow_generator(
            flow=flow,
            input_request=input_request,
            api_key_user=api_key_user,
            event_manager=event_manager,
            client_consumed_queue=client_consumed_queue,
        )
    )

    async def on_disconnect() -> None:
        logger.debug("Client disconnected, closing tasks")
        main_task.cancel()

    return StreamingResponse(
        consume_and_yield(asyncio_queue, client_consumed_queue),
        background=on_disconnect,
        media_type="text/event-stream",
    )


async def execute_flow(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    api_key_user: User,
    background_tasks: BackgroundTasks,
    *,
    stream: bool = False,
) -> RunResponse:
    """Execute a flow and handle telemetry logging."""
    telemetry_service = get_telemetry_service()
    start_time = time.perf_counter()

    try:
        result = await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=stream,
            api_key_user=api_key_user,
        )
    except ValueError as exc:
        error_msg = str(exc)
        await log_telemetry(background_tasks, telemetry_service, start_time, success=False, error_message=error_msg)

        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Resource not found: {error_msg}"
            ) from exc

        # For other ValueError cases, raise API exception
        raise APIException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, exception=exc, flow=flow) from exc

    except InvalidChatInputError as exc:
        # Don't log telemetry for invalid input as this is a user error
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid chat input: {exc!s}") from exc

    except Exception as exc:
        error_msg = str(exc)
        await log_telemetry(background_tasks, telemetry_service, start_time, success=False, error_message=error_msg)
        raise APIException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, exception=exc, flow=flow) from exc

    else:
        # Log successful execution
        await log_telemetry(background_tasks, telemetry_service, start_time, success=True)
        return result


async def process_uploaded_files(
    files: list[UploadFile] | None,
    flow_id: str,
    input_request: SimplifiedAPIRequest,
) -> SimplifiedAPIRequest:
    """Process uploaded files and update input request tweaks."""
    if not files:
        return input_request

    storage_service = get_storage_service()
    file_tweaks: dict[str, dict[str, Any]] = {}

    for file in files:
        match = FILE_NAME_PATTERN.match(file.filename)
        if not match:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file name format: {file.filename}. Must be 'ComponentName::input_name::filename'",
            )

        component_name, input_name, original_filename = match.groups()
        file_name = f"{uuid.uuid4()}_{original_filename}"

        await storage_service.save_file(flow_id=flow_id, file_name=file_name, data=await file.read())
        file_path = storage_service.build_full_path(flow_id=flow_id, file_name=file_name)

        if component_name not in file_tweaks:
            file_tweaks[component_name] = {input_name: {}}
        file_tweaks[component_name][input_name]["file_path"] = file_path

    if input_request.tweaks is None:
        input_request.tweaks = {}
    input_request.tweaks.update(file_tweaks)

    return input_request
