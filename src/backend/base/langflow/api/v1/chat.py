from __future__ import annotations

import asyncio
import json
import time
import traceback
import typing
import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlmodel import select
from starlette.background import BackgroundTask
from starlette.responses import ContentStream
from starlette.types import Receive

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    build_and_cache_graph_from_data,
    build_graph_from_data,
    build_graph_from_db,
    format_elapsed_time,
    format_exception_message,
    get_top_level_vertices,
    parse_exception,
)
from langflow.api.v1.schemas import (
    FlowDataRequest,
    InputValueRequest,
    ResultDataResponse,
    StreamData,
    VertexBuildResponse,
    VerticesOrderResponse,
)
from langflow.events.event_manager import EventManager, create_default_event_manager
from langflow.exceptions.component import ComponentBuildError
from langflow.graph.graph.base import Graph
from langflow.graph.utils import log_vertex_build
from langflow.schema.message import ErrorMessage
from langflow.schema.schema import OutputValue
from langflow.services.cache.utils import CacheMiss
from langflow.services.chat.service import ChatService
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_chat_service, get_session, get_telemetry_service, session_scope
from langflow.services.telemetry.schema import ComponentPayload, PlaygroundPayload

if TYPE_CHECKING:
    from langflow.graph.vertex.types import InterfaceVertex

router = APIRouter(tags=["Chat"])


async def try_running_celery_task(vertex, user_id):
    # Try running the task in celery
    # and set the task_id to the local vertex
    # if it fails, run the task locally
    try:
        from langflow.worker import build_vertex

        task = build_vertex.delay(vertex)
        vertex.task_id = task.id
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).debug("Error running task in celery")
        vertex.task_id = None
        await vertex.build(user_id=user_id)
    return vertex


@router.post("/build/{flow_id}/vertices")
async def retrieve_vertices_order(
    *,
    flow_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    data: Annotated[FlowDataRequest | None, Body(embed=True)] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    session: DbSession,
) -> VerticesOrderResponse:
    """Retrieve the vertices order for a given flow.

    Args:
        flow_id (str): The ID of the flow.
        background_tasks (BackgroundTasks): The background tasks.
        data (Optional[FlowDataRequest], optional): The flow data. Defaults to None.
        stop_component_id (str, optional): The ID of the stop component. Defaults to None.
        start_component_id (str, optional): The ID of the start component. Defaults to None.
        session (AsyncSession, optional): The session dependency.

    Returns:
        VerticesOrderResponse: The response containing the ordered vertex IDs and the run ID.

    Raises:
        HTTPException: If there is an error checking the build status.
    """
    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    start_time = time.perf_counter()
    components_count = None
    try:
        # First, we need to check if the flow_id is in the cache
        if not data:
            graph = await build_graph_from_db(flow_id=flow_id, session=session, chat_service=chat_service)
        else:
            graph = await build_and_cache_graph_from_data(
                flow_id=flow_id, graph_data=data.model_dump(), chat_service=chat_service
            )
        graph = graph.prepare(stop_component_id, start_component_id)

        # Now vertices is a list of lists
        # We need to get the id of each vertex
        # and return the same structure but only with the ids
        components_count = len(graph.vertices)
        vertices_to_run = list(graph.vertices_to_run.union(get_top_level_vertices(graph, graph.vertices_to_run)))
        await chat_service.set_cache(str(flow_id), graph)
        background_tasks.add_task(
            telemetry_service.log_package_playground,
            PlaygroundPayload(
                playground_seconds=int(time.perf_counter() - start_time),
                playground_component_count=components_count,
                playground_success=True,
            ),
        )
        return VerticesOrderResponse(ids=graph.first_layer, run_id=graph.run_id, vertices_to_run=vertices_to_run)
    except Exception as exc:
        background_tasks.add_task(
            telemetry_service.log_package_playground,
            PlaygroundPayload(
                playground_seconds=int(time.perf_counter() - start_time),
                playground_component_count=components_count,
                playground_success=False,
                playground_error_message=str(exc),
            ),
        )
        if "stream or streaming set to True" in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        logger.exception("Error checking build status")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/build/{flow_id}/flow")
async def build_flow(
    *,
    background_tasks: BackgroundTasks,
    flow_id: uuid.UUID,
    inputs: Annotated[InputValueRequest | None, Body(embed=True)] = None,
    data: Annotated[FlowDataRequest | None, Body(embed=True)] = None,
    files: list[str] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    log_builds: bool | None = True,
    current_user: CurrentActiveUser,
    session: DbSession,
):
    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    if not inputs:
        inputs = InputValueRequest(session=str(flow_id))

    async def build_graph_and_get_order() -> tuple[list[str], list[str], Graph]:
        start_time = time.perf_counter()
        components_count = None
        try:
            flow_id_str = str(flow_id)
            if not data:
                graph = await build_graph_from_db(flow_id=flow_id, session=session, chat_service=chat_service)
            else:
                async with session_scope() as new_session:
                    result = await new_session.exec(select(Flow.name).where(Flow.id == flow_id))
                    flow_name = result.first()
                graph = await build_graph_from_data(
                    flow_id=flow_id_str, payload=data.model_dump(), user_id=str(current_user.id), flow_name=flow_name
                )
            graph.validate_stream()
            if stop_component_id or start_component_id:
                try:
                    first_layer = graph.sort_vertices(stop_component_id, start_component_id)
                except Exception:  # noqa: BLE001
                    logger.exception("Error sorting vertices")
                    first_layer = graph.sort_vertices()
            else:
                first_layer = graph.sort_vertices()

            if inputs is not None and hasattr(inputs, "session") and inputs.session is not None:
                graph.session_id = inputs.session

            for vertex_id in first_layer:
                graph.run_manager.add_to_vertices_being_run(vertex_id)

            # Now vertices is a list of lists
            # We need to get the id of each vertex
            # and return the same structure but only with the ids
            components_count = len(graph.vertices)
            vertices_to_run = list(graph.vertices_to_run.union(get_top_level_vertices(graph, graph.vertices_to_run)))
            await chat_service.set_cache(flow_id_str, graph)
            background_tasks.add_task(
                telemetry_service.log_package_playground,
                PlaygroundPayload(
                    playground_seconds=int(time.perf_counter() - start_time),
                    playground_component_count=components_count,
                    playground_success=True,
                ),
            )
        except Exception as exc:
            background_tasks.add_task(
                telemetry_service.log_package_playground,
                PlaygroundPayload(
                    playground_seconds=int(time.perf_counter() - start_time),
                    playground_component_count=components_count,
                    playground_success=False,
                    playground_error_message=str(exc),
                ),
            )
            if "stream or streaming set to True" in str(exc):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            logger.exception("Error checking build status")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return first_layer, vertices_to_run, graph

    async def _build_vertex(vertex_id: str, graph: Graph, event_manager: EventManager) -> VertexBuildResponse:
        flow_id_str = str(flow_id)
        next_runnable_vertices = []
        top_level_vertices = []
        start_time = time.perf_counter()
        error_message = None
        try:
            vertex = graph.get_vertex(vertex_id)
            try:
                lock = chat_service.async_cache_locks[flow_id_str]
                vertex_build_result = await graph.build_vertex(
                    vertex_id=vertex_id,
                    user_id=str(current_user.id),
                    inputs_dict=inputs.model_dump() if inputs else {},
                    files=files,
                    get_cache=chat_service.get_cache,
                    set_cache=chat_service.set_cache,
                    event_manager=event_manager,
                )
                result_dict = vertex_build_result.result_dict
                params = vertex_build_result.params
                valid = vertex_build_result.valid
                artifacts = vertex_build_result.artifacts
                next_runnable_vertices = await graph.get_next_runnable_vertices(lock, vertex=vertex, cache=False)
                top_level_vertices = graph.get_top_level_vertices(next_runnable_vertices)

                result_data_response = ResultDataResponse.model_validate(result_dict, from_attributes=True)
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, ComponentBuildError):
                    params = exc.message
                    tb = exc.formatted_traceback
                else:
                    tb = traceback.format_exc()
                    logger.exception("Error building Component")
                    params = format_exception_message(exc)
                message = {"errorMessage": params, "stackTrace": tb}
                valid = False
                error_message = params
                output_label = vertex.outputs[0]["name"] if vertex.outputs else "output"
                outputs = {output_label: OutputValue(message=message, type="error")}
                result_data_response = ResultDataResponse(results={}, outputs=outputs)
                artifacts = {}
                background_tasks.add_task(graph.end_all_traces, error=exc)

            result_data_response.message = artifacts

            # Log the vertex build
            if not vertex.will_stream and log_builds:
                background_tasks.add_task(
                    log_vertex_build,
                    flow_id=flow_id_str,
                    vertex_id=vertex_id,
                    valid=valid,
                    params=params,
                    data=result_data_response,
                    artifacts=artifacts,
                )
            else:
                await chat_service.set_cache(flow_id_str, graph)

            timedelta = time.perf_counter() - start_time
            duration = format_elapsed_time(timedelta)
            result_data_response.duration = duration
            result_data_response.timedelta = timedelta
            vertex.add_build_time(timedelta)
            inactivated_vertices = list(graph.inactivated_vertices)
            graph.reset_inactivated_vertices()
            graph.reset_activated_vertices()
            # graph.stop_vertex tells us if the user asked
            # to stop the build of the graph at a certain vertex
            # if it is in next_vertices_ids, we need to remove other
            # vertices from next_vertices_ids
            if graph.stop_vertex and graph.stop_vertex in next_runnable_vertices:
                next_runnable_vertices = [graph.stop_vertex]

            if not graph.run_manager.vertices_being_run and not next_runnable_vertices:
                background_tasks.add_task(graph.end_all_traces)

            build_response = VertexBuildResponse(
                inactivated_vertices=list(set(inactivated_vertices)),
                next_vertices_ids=list(set(next_runnable_vertices)),
                top_level_vertices=list(set(top_level_vertices)),
                valid=valid,
                params=params,
                id=vertex.id,
                data=result_data_response,
            )
            background_tasks.add_task(
                telemetry_service.log_package_component,
                ComponentPayload(
                    component_name=vertex_id.split("-")[0],
                    component_seconds=int(time.perf_counter() - start_time),
                    component_success=valid,
                    component_error_message=error_message,
                ),
            )
        except Exception as exc:
            background_tasks.add_task(
                telemetry_service.log_package_component,
                ComponentPayload(
                    component_name=vertex_id.split("-")[0],
                    component_seconds=int(time.perf_counter() - start_time),
                    component_success=False,
                    component_error_message=str(exc),
                ),
            )
            logger.exception("Error building Component")
            message = parse_exception(exc)
            raise HTTPException(status_code=500, detail=message) from exc

        return build_response

    async def build_vertices(
        vertex_id: str,
        graph: Graph,
        client_consumed_queue: asyncio.Queue,
        event_manager: EventManager,
    ) -> None:
        build_task = asyncio.create_task(_build_vertex(vertex_id, graph, event_manager))
        try:
            await build_task
        except asyncio.CancelledError as exc:
            logger.exception(exc)
            build_task.cancel()
            return

        vertex_build_response: VertexBuildResponse = build_task.result()
        # send built event or error event
        try:
            vertex_build_response_json = vertex_build_response.model_dump_json()
            build_data = json.loads(vertex_build_response_json)
        except Exception as exc:
            msg = f"Error serializing vertex build response: {exc}"
            raise ValueError(msg) from exc
        event_manager.on_end_vertex(data={"build_data": build_data})
        await client_consumed_queue.get()
        if vertex_build_response.valid and vertex_build_response.next_vertices_ids:
            tasks = []
            for next_vertex_id in vertex_build_response.next_vertices_ids:
                task = asyncio.create_task(build_vertices(next_vertex_id, graph, client_consumed_queue, event_manager))
                tasks.append(task)
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                for task in tasks:
                    task.cancel()
                return

    async def event_generator(event_manager: EventManager, client_consumed_queue: asyncio.Queue) -> None:
        if not data:
            # using another task since the build_graph_and_get_order is now an async function
            vertices_task = asyncio.create_task(build_graph_and_get_order())
            try:
                await vertices_task
            except asyncio.CancelledError:
                vertices_task.cancel()
                return
            except Exception as e:
                error_message = ErrorMessage(
                    flow_id=flow_id,
                    exception=e,
                )
                event_manager.on_error(data=error_message.data)
                raise

            ids, vertices_to_run, graph = vertices_task.result()
        else:
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
        await client_consumed_queue.get()

        tasks = []
        for vertex_id in ids:
            task = asyncio.create_task(build_vertices(vertex_id, graph, client_consumed_queue, event_manager))
            tasks.append(task)
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            background_tasks.add_task(graph.end_all_traces)
            for task in tasks:
                task.cancel()
            return
        except Exception as e:
            logger.error(f"Error building vertices: {e}")
            custom_component = graph.get_vertex(vertex_id).custom_component
            trace_name = getattr(custom_component, "trace_name", None)
            error_message = ErrorMessage(
                flow_id=flow_id,
                exception=e,
                session_id=graph.session_id,
                trace_name=trace_name,
            )
            event_manager.on_error(data=error_message.data)
            raise
        event_manager.on_end(data={})
        await event_manager.queue.put((None, None, time.time))

    async def consume_and_yield(queue: asyncio.Queue, client_consumed_queue: asyncio.Queue) -> typing.AsyncGenerator:
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

    asyncio_queue: asyncio.Queue = asyncio.Queue()
    asyncio_queue_client_consumed: asyncio.Queue = asyncio.Queue()
    event_manager = create_default_event_manager(queue=asyncio_queue)
    main_task = asyncio.create_task(event_generator(event_manager, asyncio_queue_client_consumed))

    def on_disconnect() -> None:
        logger.debug("Client disconnected, closing tasks")
        main_task.cancel()

    return DisconnectHandlerStreamingResponse(
        consume_and_yield(asyncio_queue, asyncio_queue_client_consumed),
        media_type="application/x-ndjson",
        on_disconnect=on_disconnect,
    )


class DisconnectHandlerStreamingResponse(StreamingResponse):
    def __init__(
        self,
        content: ContentStream,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
        on_disconnect: typing.Callable | None = None,
    ):
        super().__init__(content, status_code, headers, media_type, background)
        self.on_disconnect = on_disconnect

    async def listen_for_disconnect(self, receive: Receive) -> None:
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                if self.on_disconnect:
                    coro = self.on_disconnect()
                    if asyncio.iscoroutine(coro):
                        await coro
                break


@router.post("/build/{flow_id}/vertices/{vertex_id}")
async def build_vertex(
    *,
    flow_id: uuid.UUID,
    vertex_id: str,
    background_tasks: BackgroundTasks,
    inputs: Annotated[InputValueRequest | None, Body(embed=True)] = None,
    files: list[str] | None = None,
    current_user: CurrentActiveUser,
) -> VertexBuildResponse:
    """Build a vertex instead of the entire graph.

    Args:
        flow_id (str): The ID of the flow.
        vertex_id (str): The ID of the vertex to build.
        background_tasks (BackgroundTasks): The background tasks dependency.
        inputs (Optional[InputValueRequest], optional): The input values for the vertex. Defaults to None.
        files (List[str], optional): The files to use. Defaults to None.
        current_user (Any, optional): The current user dependency. Defaults to Depends(get_current_active_user).

    Returns:
        VertexBuildResponse: The response containing the built vertex information.

    Raises:
        HTTPException: If there is an error building the vertex.

    """
    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    flow_id_str = str(flow_id)

    next_runnable_vertices = []
    top_level_vertices = []
    start_time = time.perf_counter()
    error_message = None
    try:
        graph: Graph = await chat_service.get_cache(flow_id_str)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Graph not found") from exc

    try:
        cache = await chat_service.get_cache(flow_id_str)
        if isinstance(cache, CacheMiss):
            # If there's no cache
            logger.warning(f"No cache found for {flow_id_str}. Building graph starting at {vertex_id}")
            graph = await build_graph_from_db(
                flow_id=flow_id, session=await anext(get_session()), chat_service=chat_service
            )
        else:
            graph = cache.get("result")
            await graph.initialize_run()
        vertex = graph.get_vertex(vertex_id)

        try:
            lock = chat_service.async_cache_locks[flow_id_str]
            vertex_build_result = await graph.build_vertex(
                vertex_id=vertex_id,
                user_id=str(current_user.id),
                inputs_dict=inputs.model_dump() if inputs else {},
                files=files,
                get_cache=chat_service.get_cache,
                set_cache=chat_service.set_cache,
            )
            result_dict = vertex_build_result.result_dict
            params = vertex_build_result.params
            valid = vertex_build_result.valid
            artifacts = vertex_build_result.artifacts
            next_runnable_vertices = await graph.get_next_runnable_vertices(lock, vertex=vertex, cache=False)
            top_level_vertices = graph.get_top_level_vertices(next_runnable_vertices)
            result_data_response = ResultDataResponse.model_validate(result_dict, from_attributes=True)
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, ComponentBuildError):
                params = exc.message
                tb = exc.formatted_traceback
            else:
                tb = traceback.format_exc()
                logger.exception("Error building Component")
                params = format_exception_message(exc)
            message = {"errorMessage": params, "stackTrace": tb}
            valid = False
            error_message = params
            output_label = vertex.outputs[0]["name"] if vertex.outputs else "output"
            outputs = {output_label: OutputValue(message=message, type="error")}
            result_data_response = ResultDataResponse(results={}, outputs=outputs)
            artifacts = {}
            background_tasks.add_task(graph.end_all_traces, error=exc)
            # If there's an error building the vertex
            # we need to clear the cache
            await chat_service.clear_cache(flow_id_str)

        result_data_response.message = artifacts

        # Log the vertex build
        if not vertex.will_stream:
            background_tasks.add_task(
                log_vertex_build,
                flow_id=flow_id_str,
                vertex_id=vertex_id,
                valid=valid,
                params=params,
                data=result_data_response,
                artifacts=artifacts,
            )

        timedelta = time.perf_counter() - start_time
        duration = format_elapsed_time(timedelta)
        result_data_response.duration = duration
        result_data_response.timedelta = timedelta
        vertex.add_build_time(timedelta)
        inactivated_vertices = list(graph.inactivated_vertices)
        graph.reset_inactivated_vertices()
        graph.reset_activated_vertices()

        await chat_service.set_cache(flow_id_str, graph)

        # graph.stop_vertex tells us if the user asked
        # to stop the build of the graph at a certain vertex
        # if it is in next_vertices_ids, we need to remove other
        # vertices from next_vertices_ids
        if graph.stop_vertex and graph.stop_vertex in next_runnable_vertices:
            next_runnable_vertices = [graph.stop_vertex]

        if not graph.run_manager.vertices_being_run and not next_runnable_vertices:
            background_tasks.add_task(graph.end_all_traces)

        build_response = VertexBuildResponse(
            inactivated_vertices=list(set(inactivated_vertices)),
            next_vertices_ids=list(set(next_runnable_vertices)),
            top_level_vertices=list(set(top_level_vertices)),
            valid=valid,
            params=params,
            id=vertex.id,
            data=result_data_response,
        )
        background_tasks.add_task(
            telemetry_service.log_package_component,
            ComponentPayload(
                component_name=vertex_id.split("-")[0],
                component_seconds=int(time.perf_counter() - start_time),
                component_success=valid,
                component_error_message=error_message,
            ),
        )
    except Exception as exc:
        background_tasks.add_task(
            telemetry_service.log_package_component,
            ComponentPayload(
                component_name=vertex_id.split("-")[0],
                component_seconds=int(time.perf_counter() - start_time),
                component_success=False,
                component_error_message=str(exc),
            ),
        )
        logger.exception("Error building Component")
        message = parse_exception(exc)
        raise HTTPException(status_code=500, detail=message) from exc

    return build_response


async def _stream_vertex(flow_id: str, vertex_id: str, chat_service: ChatService):
    graph = None
    try:
        try:
            cache = await chat_service.get_cache(flow_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error building Component")
            yield str(StreamData(event="error", data={"error": str(exc)}))
            return

        if isinstance(cache, CacheMiss):
            # If there's no cache
            msg = f"No cache found for {flow_id}."
            logger.error(msg)
            yield str(StreamData(event="error", data={"error": msg}))
            return
        else:
            graph = cache.get("result")

        try:
            vertex: InterfaceVertex = graph.get_vertex(vertex_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error building Component")
            yield str(StreamData(event="error", data={"error": str(exc)}))
            return

        if not hasattr(vertex, "stream"):
            msg = f"Vertex {vertex_id} does not support streaming"
            logger.error(msg)
            yield str(StreamData(event="error", data={"error": msg}))
            return

        if isinstance(vertex.built_result, str) and vertex.built_result:
            stream_data = StreamData(
                event="message",
                data={"message": f"Streaming vertex {vertex_id}"},
            )
            yield str(stream_data)
            stream_data = StreamData(
                event="message",
                data={"chunk": vertex.built_result},
            )
            yield str(stream_data)

        elif not vertex.frozen or not vertex.built:
            logger.debug(f"Streaming vertex {vertex_id}")
            stream_data = StreamData(
                event="message",
                data={"message": f"Streaming vertex {vertex_id}"},
            )
            yield str(stream_data)
            try:
                async for chunk in vertex.stream():
                    stream_data = StreamData(
                        event="message",
                        data={"chunk": chunk},
                    )
                    yield str(stream_data)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error building Component")
                exc_message = parse_exception(exc)
                if exc_message == "The message must be an iterator or an async iterator.":
                    exc_message = "This stream has already been closed."
                yield str(StreamData(event="error", data={"error": exc_message}))
        elif vertex.result is not None:
            stream_data = StreamData(
                event="message",
                data={"chunk": vertex.built_result},
            )
            yield str(stream_data)
        else:
            msg = f"No result found for vertex {vertex_id}"
            logger.error(msg)
            yield str(StreamData(event="error", data={"error": msg}))
            return
    finally:
        logger.debug("Closing stream")
        if graph:
            await chat_service.set_cache(flow_id, graph)
        yield str(StreamData(event="close", data={"message": "Stream closed"}))


@router.get("/build/{flow_id}/{vertex_id}/stream", response_class=StreamingResponse)
async def build_vertex_stream(
    flow_id: uuid.UUID,
    vertex_id: str,
):
    """Build a vertex instead of the entire graph.

    This function is responsible for building a single vertex instead of the entire graph.
    It takes the `flow_id` and `vertex_id` as required parameters, and an optional `session_id`.
    It also depends on the `ChatService` and `SessionService` services.

    If `session_id` is not provided, it retrieves the graph from the cache using the `chat_service`.
    If `session_id` is provided, it loads the session data using the `session_service`.

    Once the graph is obtained, it retrieves the specified vertex using the `vertex_id`.
    If the vertex does not support streaming, an error is raised.
    If the vertex has a built result, it sends the result as a chunk.
    If the vertex is not frozen or not built, it streams the vertex data.
    If the vertex has a result, it sends the result as a chunk.
    If none of the above conditions are met, an error is raised.

    If any exception occurs during the process, an error message is sent.
    Finally, the stream is closed.

    Returns:
        A `StreamingResponse` object with the streamed vertex data in text/event-stream format.

    Raises:
        HTTPException: If an error occurs while building the vertex.
    """
    try:
        return StreamingResponse(
            _stream_vertex(str(flow_id), vertex_id, get_chat_service()), media_type="text/event-stream"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error building Component") from exc
