import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import BackgroundTasks, HTTPException, Response
from loguru import logger
from sqlmodel import select

from langflow.api.disconnect import DisconnectHandlerStreamingResponse
from langflow.api.utils import (
    CurrentActiveUser,
    EventDeliveryType,
    build_graph_from_data,
    build_graph_from_db,
    get_top_level_vertices,
)
from langflow.api.v1.schemas import (
    FlowDataRequest,
    InputValueRequest,
    ResultDataResponse,
    VertexBuildResponse,
)
from langflow.events.event_manager import EventManager
from langflow.graph.graph.base import Graph
from langflow.graph.graph.constants import Finish
from langflow.graph.utils import log_vertex_build
from langflow.schema.message import ErrorMessage
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_chat_service, get_telemetry_service, session_scope
from langflow.services.job_queue.service import JobQueueNotFoundError, JobQueueService
from langflow.services.telemetry.schema import ComponentPayload, PlaygroundPayload


async def start_flow_build(
    *,
    flow_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    inputs: InputValueRequest | None,
    data: FlowDataRequest | None,
    files: list[str] | None,
    stop_component_id: str | None,
    start_component_id: str | None,
    log_builds: bool,
    current_user: CurrentActiveUser,
    queue_service: JobQueueService,
    flow_name: str | None = None,
) -> str:
    """Start the flow build process by setting up the queue and starting the build task.

    Returns:
        the job_id.
    """
    job_id = str(uuid.uuid4())
    try:
        _, event_manager = queue_service.create_queue(job_id)
        task_coro = generate_flow_events(
            flow_id=flow_id,
            background_tasks=background_tasks,
            event_manager=event_manager,
            inputs=inputs,
            data=data,
            files=files,
            stop_component_id=stop_component_id,
            start_component_id=start_component_id,
            log_builds=log_builds,
            current_user=current_user,
            flow_name=flow_name,
        )
        queue_service.start_job(job_id, task_coro)
    except Exception as e:
        logger.exception("Failed to create queue and start task")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return job_id


async def get_flow_events_response(
    *,
    job_id: str,
    queue_service: JobQueueService,
    event_delivery: EventDeliveryType,
):
    """Get events for a specific build job, either as a stream or single event."""
    try:
        main_queue, event_manager, event_task, _ = queue_service.get_queue_data(job_id)
        if event_delivery in (EventDeliveryType.STREAMING, EventDeliveryType.DIRECT):
            if event_task is None:
                logger.error(f"No event task found for job {job_id}")
                raise HTTPException(status_code=404, detail="No event task found for job")
            return await create_flow_response(
                queue=main_queue,
                event_manager=event_manager,
                event_task=event_task,
            )

        # Polling mode - get all available events
        try:
            events: list = []
            # Get all available events from the queue without blocking
            while not main_queue.empty():
                _, value, _ = await main_queue.get()
                if value is None:
                    # End of stream, trigger end event
                    if event_task is not None:
                        event_task.cancel()
                    event_manager.on_end(data={})
                    # Include the end event
                    events.append(None)
                    break
                events.append(value.decode("utf-8"))

            # If no events were available, wait for one (with timeout)
            if not events:
                _, value, _ = await main_queue.get()
                if value is None:
                    # End of stream, trigger end event
                    if event_task is not None:
                        event_task.cancel()
                    event_manager.on_end(data={})
                else:
                    events.append(value.decode("utf-8"))

            # Return as NDJSON format - each line is a complete JSON object
            content = "\n".join([event for event in events if event is not None])
            return Response(content=content, media_type="application/x-ndjson")
        except asyncio.CancelledError as exc:
            logger.info(f"Event polling was cancelled for job {job_id}")
            raise HTTPException(status_code=499, detail="Event polling was cancelled") from exc
        except asyncio.TimeoutError:
            logger.warning(f"Timeout while waiting for events for job {job_id}")
            return Response(content="", media_type="application/x-ndjson")  # Return empty response instead of error

    except JobQueueNotFoundError as exc:
        logger.error(f"Job not found: {job_id}. Error: {exc!s}")
        raise HTTPException(status_code=404, detail=f"Job not found: {exc!s}") from exc
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        logger.exception(f"Unexpected error processing flow events for job {job_id}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc!s}") from exc


async def create_flow_response(
    queue: asyncio.Queue,
    event_manager: EventManager,
    event_task: asyncio.Task,
) -> DisconnectHandlerStreamingResponse:
    """Create a streaming response for the flow build process."""

    async def consume_and_yield() -> AsyncIterator[str]:
        while True:
            try:
                event_id, value, put_time = await queue.get()
                if value is None:
                    break
                get_time = time.time()
                yield value.decode("utf-8")
                logger.debug(f"Event {event_id} consumed in {get_time - put_time:.4f}s")
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"Error consuming event: {exc}")
                break

    def on_disconnect() -> None:
        logger.debug("Client disconnected, closing tasks")
        event_task.cancel()
        event_manager.on_end(data={})

    return DisconnectHandlerStreamingResponse(
        consume_and_yield(),
        media_type="application/x-ndjson",
        on_disconnect=on_disconnect,
    )


async def generate_flow_events(
    *,
    flow_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    event_manager: EventManager,
    inputs: InputValueRequest | None,
    data: FlowDataRequest | None,
    files: list[str] | None,
    stop_component_id: str | None,
    start_component_id: str | None,
    log_builds: bool,
    current_user: CurrentActiveUser,
    flow_name: str | None = None,
) -> None:
    """Generate events for flow building process.

    This function handles the core flow building logic and generates appropriate events:
    - Building and validating the graph
    - Processing vertices
    - Handling errors and cleanup
    """
    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    if not inputs:
        inputs = InputValueRequest(session=str(flow_id))

    async def build_graph_and_get_order() -> tuple[list[str], list[str], Graph]:
        start_time = time.perf_counter()
        components_count = 0
        graph = None
        try:
            flow_id_str = str(flow_id)
            # Create a fresh session for database operations
            async with session_scope() as fresh_session:
                graph = await create_graph(fresh_session, flow_id_str, flow_name)

            first_layer = sort_vertices(graph)

            for vertex_id in first_layer:
                graph.run_manager.add_to_vertices_being_run(vertex_id)

            # Now vertices is a list of lists
            # We need to get the id of each vertex
            # and return the same structure but only with the ids
            components_count = len(graph.vertices)
            vertices_to_run = list(graph.vertices_to_run.union(get_top_level_vertices(graph, graph.vertices_to_run)))

            await chat_service.set_cache(flow_id_str, graph)
            await log_telemetry(start_time, components_count, success=True)

        except Exception as exc:
            await log_telemetry(start_time, components_count, success=False, error_message=str(exc))

            if "stream or streaming set to True" in str(exc):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            logger.exception("Error checking build status")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return first_layer, vertices_to_run, graph

    async def log_telemetry(
        start_time: float, components_count: int, *, success: bool, error_message: str | None = None
    ):
        background_tasks.add_task(
            telemetry_service.log_package_playground,
            PlaygroundPayload(
                playground_seconds=int(time.perf_counter() - start_time),
                playground_component_count=components_count,
                playground_success=success,
                playground_error_message=str(error_message) if error_message else "",
            ),
        )

    async def create_graph(fresh_session, flow_id_str: str, flow_name: str | None) -> Graph:
        if inputs is not None and getattr(inputs, "session", None) is not None:
            effective_session_id = inputs.session
        else:
            effective_session_id = flow_id_str

        if not data:
            return await build_graph_from_db(
                flow_id=flow_id,
                session=fresh_session,
                chat_service=chat_service,
                user_id=str(current_user.id),
                session_id=effective_session_id,
            )

        if not flow_name:
            result = await fresh_session.exec(select(Flow.name).where(Flow.id == flow_id))
            flow_name = result.first()

        return await build_graph_from_data(
            flow_id=flow_id_str,
            payload=data.model_dump(),
            user_id=str(current_user.id),
            flow_name=flow_name,
            session_id=effective_session_id,
        )

    def sort_vertices(graph: Graph) -> list[str]:
        try:
            return graph.sort_vertices(stop_component_id, start_component_id)
        except Exception:  # noqa: BLE001
            logger.exception("Error sorting vertices")
            return graph.sort_vertices()

    try:
        ids, vertices_to_run, graph = await build_graph_and_get_order()
    except Exception as e:
        error_message = ErrorMessage(
            flow_id=flow_id,
            exception=e,
        )
        event_manager.on_error(data=error_message.data)
        raise

    event_manager.on_vertices_sorted(data={"ids": ids, "to_run": vertices_to_run})

    # ----------------------------------------------------------------------------------
    # Refactored logic: use graph.async_start to process the graph sequentially and emit
    # the required events as each vertex finishes building.
    # ----------------------------------------------------------------------------------
    try:
        # Prepare the graph for execution - this was missing and caused "Graph not prepared" error
        graph.prepare(stop_component_id, start_component_id)

        # Use async_start to process the graph and emit events for each vertex completion
        # This is cleaner than manually managing the astep loop
        async def build_with_astep():
            flow_id_str = str(flow_id)

            # Set session_id on components that have it
            # I don't know why this is needed, but it is
            if inputs and inputs.session:
                for vertex in graph.vertices:
                    if hasattr(vertex, "has_session_id") and vertex.has_session_id:
                        vertex.update_raw_params({"session_id": inputs.session}, overwrite=True)

            # Track start time for component execution timing
            step_start_time = time.perf_counter()

            try:
                # Use async_start with empty inputs since we've already set the values on vertices
                async for step_result in graph.async_start(
                    inputs=[inputs.model_dump()],
                    event_manager=event_manager,
                    files=files,
                    user_id=str(current_user.id),
                ):
                    # Skip if this is the Finish result
                    if isinstance(step_result, Finish):
                        break

                    # Get the vertex and build information from step_result
                    vertex = step_result.vertex

                    # For async_start, we need to get the next_runnable_vertices differently
                    # since we don't have direct access to the queue changes.
                    # We can get them from the current graph state after the step
                    next_runnable_vertices = list(graph._run_queue)
                    top_level_vertices = (
                        graph.get_top_level_vertices(next_runnable_vertices) if next_runnable_vertices else []
                    )
                    inactivated_vertices = []  # async_start already manages these

                    # Create the VertexBuildResponse that matches the original format
                    build_response = VertexBuildResponse(
                        id=vertex.id,
                        inactivated_vertices=inactivated_vertices,
                        next_vertices_ids=next_runnable_vertices,
                        top_level_vertices=top_level_vertices,
                        valid=step_result.valid,
                        params=step_result.params,
                        data=ResultDataResponse.model_validate(step_result.result_dict, from_attributes=True),
                    )

                    # Serialize to JSON and back to ensure proper formatting (matches original implementation)
                    vertex_build_response_json = build_response.model_dump_json()
                    build_data = json.loads(vertex_build_response_json)

                    # Log vertex build if needed (replicating original behavior)
                    if not vertex.will_stream and log_builds:
                        try:
                            result_data_response = ResultDataResponse.model_validate(
                                step_result.result_dict, from_attributes=True
                            )
                            result_data_response.message = step_result.artifacts
                            background_tasks.add_task(
                                log_vertex_build,
                                flow_id=flow_id_str,
                                vertex_id=vertex.id,
                                valid=step_result.valid,
                                params=step_result.params,
                                data=result_data_response,
                                artifacts=step_result.artifacts,
                            )
                        except (ValueError, TypeError) as exc:
                            # Don't fail the whole process if logging fails
                            logger.warning(f"Failed to log vertex build for {vertex.id}: {exc}")
                        except Exception as exc:  # noqa: BLE001
                            # Don't fail the whole process if logging fails
                            logger.warning(f"Unexpected error logging vertex build for {vertex.id}: {exc}")
                    else:
                        await chat_service.set_cache(flow_id_str, graph)

                    # Calculate component execution time
                    # Since async_start doesn't provide timing info directly, we need to track it
                    # We'll use the current time as an approximation for the step completion time
                    component_execution_time = int(time.perf_counter() - step_start_time)

                    # Log telemetry for the component
                    background_tasks.add_task(
                        telemetry_service.log_package_component,
                        ComponentPayload(
                            component_name=vertex.id.split("-")[0],
                            component_seconds=component_execution_time,
                            component_success=step_result.valid,
                            component_error_message=None,
                        ),
                    )

                    # Emit the vertex completion event
                    # NOTE: We don't emit on_build_start/on_build_end events here like in ComponentToolkit.
                    # Those events are only used when components are used as tools. For flow building,
                    # the UI shows build progress information through the next_vertices_ids field
                    # in the VertexBuildResponse, which indicates which vertices will be built next.
                    event_manager.on_end_vertex(data={"build_data": build_data})

                    # Reset timer for next step
                    step_start_time = time.perf_counter()

            except StopAsyncIteration:
                # Normal completion of async generator
                pass
            except Exception as e:
                logger.error(f"Error in async_start: {e}")
                raise

        # Execute the build process
        await build_with_astep()

    except asyncio.CancelledError:
        background_tasks.add_task(graph.end_all_traces_in_context())
        raise
    except Exception as e:
        logger.error(f"Error building vertices: {e}")
        some_vertex_id = next(iter(graph.vertex_map.keys()))
        custom_component = graph.get_vertex(some_vertex_id).custom_component
        trace_name = getattr(custom_component, "trace_name", None)
        error_message = ErrorMessage(
            flow_id=flow_id,
            exception=e,
            session_id=graph.session_id,
            trace_name=trace_name,
        )
        event_manager.on_error(data=error_message.data)
        raise

    # Signal completion
    event_manager.on_end(data={})
    await graph.end_all_traces()
    await event_manager.queue.put((None, None, time.time()))


async def cancel_flow_build(
    *,
    job_id: str,
    queue_service: JobQueueService,
) -> bool:
    """Cancel an ongoing flow build job.

    Args:
        job_id: The unique identifier of the job to cancel
        queue_service: The service managing job queues

    Returns:
        True if the job was successfully canceled or doesn't need cancellation
        False if the cancellation failed

    Raises:
        ValueError: If the job doesn't exist
        asyncio.CancelledError: If the task cancellation failed
    """
    # Get the event task and event manager for the job
    _, _, event_task, _ = queue_service.get_queue_data(job_id)

    if event_task is None:
        logger.warning(f"No event task found for job_id {job_id}")
        return True  # Nothing to cancel is still a success

    if event_task.done():
        logger.info(f"Task for job_id {job_id} is already completed")
        return True  # Nothing to cancel is still a success

    # Store the task reference to check status after cleanup
    task_before_cleanup = event_task

    try:
        # Perform cleanup using the queue service
        await queue_service.cleanup_job(job_id)
    except asyncio.CancelledError:
        # Check if the task was actually cancelled
        if task_before_cleanup.cancelled():
            logger.info(f"Successfully cancelled flow build for job_id {job_id} (CancelledError caught)")
            return True
        # If the task wasn't cancelled, re-raise the exception
        logger.error(f"CancelledError caught but task for job_id {job_id} was not cancelled")
        raise

    # If no exception was raised, verify that the task was actually cancelled
    # The task should be done (cancelled) after cleanup
    if task_before_cleanup.cancelled():
        logger.info(f"Successfully cancelled flow build for job_id {job_id}")
        return True

    # If we get here, the task wasn't cancelled properly
    logger.error(f"Failed to cancel flow build for job_id {job_id}, task is still running")
    return False
