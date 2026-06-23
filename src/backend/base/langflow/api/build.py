import asyncio
import json
import time
import traceback
import uuid
from collections.abc import AsyncIterator

from fastapi import BackgroundTasks, HTTPException, Response
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.base import Graph
from lfx.graph.utils import log_vertex_build
from lfx.graph.vertex.base import Vertex
from lfx.log.logger import logger
from lfx.schema.schema import InputValueRequest
from sqlmodel import select

from langflow.api.disconnect import DisconnectHandlerStreamingResponse
from langflow.api.utils import (
    CurrentActiveUser,
    EventDeliveryType,
    build_graph_from_data,
    build_graph_from_db,
    format_elapsed_time,
    format_exception_message,
    get_top_level_vertices,
    parse_exception,
)
from langflow.api.v1.schemas import (
    FlowDataRequest,
    ResultDataResponse,
    VertexBuildResponse,
)
from langflow.events.event_manager import EventManager
from langflow.exceptions.component import ComponentBuildError
from langflow.schema.message import ErrorMessage
from langflow.schema.schema import OutputValue
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobType
from langflow.services.deps import (
    get_chat_service,
    get_job_service,
    get_memory_base_service,
    get_task_service,
    get_telemetry_service,
    session_scope,
)
from langflow.services.job_queue.service import JobQueueNotFoundError, JobQueueService
from langflow.services.telemetry.schema import (
    ComponentInputsPayload,
    ComponentPayload,
    PlaygroundPayload,
)

# Interval (seconds) at which the streaming response's heartbeat refreshes
# the polling-watchdog activity key. Exposed at module scope so tests can
# patch it down for fast verification of the heartbeat task itself.
STREAMING_ACTIVITY_REFRESH_S = 10.0


def _output_meta_for_vertex(graph: Graph, vertex_id: str) -> dict:
    """Authoritative per-output metadata for the v2 ``output`` stream event.

    Sourced from the real graph vertex (the only place ``display_name`` /
    ``is_output`` / declared output types are authoritative) so the streamed
    ``OutputEvent`` matches the sync ``outputs[id]`` ``ComponentOutput``. Shipped as
    an additive ``output_meta`` key on ``end_vertex``; existing consumers read
    ``build_data`` and ignore this. ``is_terminal`` mirrors the sync ``outputs`` set
    so the stream emits an ``output`` event for exactly the same components.
    """
    vertex = graph.get_vertex(vertex_id)
    output_types = vertex.outputs[0].get("types", []) if (vertex.outputs and len(vertex.outputs) > 0) else []
    try:
        terminal_ids = set(graph.get_terminal_nodes())
    except AttributeError:
        terminal_ids = {v.id for v in graph.vertices if not graph.successor_map.get(v.id, [])}
    return {
        "component_id": vertex.id,
        "display_name": vertex.display_name or vertex.vertex_type,
        "vertex_type": vertex.vertex_type,
        "is_output": bool(vertex.is_output),
        "is_terminal": vertex_id in terminal_ids,
        "output_types": output_types,
    }


def _rerun_non_input_predecessors(graph: Graph, vertex_id: str) -> None:
    """Un-build the paused vertex's non-input predecessors so they re-run on resume.

    A checkpoint cannot serialize non-JSON outputs (Tools, models), so a producer like
    an Agent would receive ``None`` tools after restore. Re-running the upstream
    definitions regenerates valid inputs; input vertices (e.g. Chat Input) keep their
    restored value and are not re-run.
    """
    visited: set[str] = set()
    stack = list(graph.predecessor_map.get(vertex_id, []))
    while stack:
        pred_id = stack.pop()
        if pred_id in visited:
            continue
        visited.add(pred_id)
        try:
            pred = graph.get_vertex(pred_id)
        except ValueError:
            continue
        if pred.is_input:
            continue
        pred.built = False
        stack.extend(graph.predecessor_map.get(pred_id, []))


def _log_component_input_telemetry(
    vertex,
    vertex_id: str,
    component_run_id: str,
    background_tasks: BackgroundTasks,
    telemetry_service,
) -> None:
    """Log component input telemetry if available."""
    if hasattr(vertex, "custom_component") and vertex.custom_component:
        inputs_dict = vertex.custom_component.get_telemetry_input_values()
        if inputs_dict:
            background_tasks.add_task(
                telemetry_service.log_package_component_inputs,
                ComponentInputsPayload(
                    component_run_id=component_run_id,
                    component_id=vertex_id,
                    component_name=vertex_id.split("-")[0],
                    component_inputs=inputs_dict,
                ),
            )


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
    source_flow_id: uuid.UUID | None = None,
) -> str:
    """Start the flow build process by setting up the queue and starting the build task.

    Args:
        flow_id: The flow ID used for tracking, sessions, and messages.
        background_tasks: FastAPI background tasks for async operations.
        inputs: Optional input values for the flow.
        data: Optional flow data request.
        files: Optional list of file paths.
        stop_component_id: Optional component ID to stop at.
        start_component_id: Optional component ID to start from.
        log_builds: Whether to log build events.
        current_user: The currently authenticated user.
        queue_service: The job queue service instance.
        flow_name: Optional flow name override.
        source_flow_id: If provided, the actual flow ID to load from DB.
            Used by public flows where flow_id is a virtual UUID for session isolation
            but the flow data must be loaded from the original flow in the database.

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
            source_flow_id=source_flow_id,
        )
        queue_service.start_job(job_id, task_coro)
    except Exception as e:
        await logger.aexception("Failed to create queue and start task")
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
        # Refresh the polling-watchdog heartbeat for any client-driven access
        # (polling and streaming both count as "client alive"). No-op for the
        # in-memory queue or when the watchdog is disabled.
        touch = getattr(queue_service, "touch_activity", None)
        if touch is not None:
            await touch(job_id)
        if event_delivery in (EventDeliveryType.STREAMING, EventDeliveryType.DIRECT):
            return await create_flow_response(
                queue=main_queue,
                event_manager=event_manager,
                event_task=event_task,
                queue_service=queue_service,
                job_id=job_id,
            )

        if event_delivery != EventDeliveryType.POLLING:
            # Defensive exhaustiveness check: if a new EventDeliveryType is added
            # without wiring it up here, surface a clear error instead of silently
            # treating it as polling. Each delivery mode has different cross-worker
            # guarantees (DIRECT/STREAMING use signal_cancel + heartbeat; POLLING
            # uses the watchdog), so silent fallthrough hides real configuration
            # bugs in multi-worker Redis setups.
            supported = ", ".join(sorted(t.value for t in EventDeliveryType))
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported event_delivery {event_delivery!r}. "
                    f"Use one of: {supported}. "
                    "For multi-worker Redis deployments, all three values are supported; "
                    "set LANGFLOW_EVENT_DELIVERY to override the default."
                ),
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
            await logger.ainfo(f"Event polling was cancelled for job {job_id}")
            raise HTTPException(status_code=499, detail="Event polling was cancelled") from exc
        except asyncio.TimeoutError:
            await logger.awarning(f"Timeout while waiting for events for job {job_id}")
            return Response(content="", media_type="application/x-ndjson")  # Return empty response instead of error

    except JobQueueNotFoundError as exc:
        await logger.aerror(f"Job not found: {job_id}. Error: {exc!s}")
        raise HTTPException(status_code=404, detail=f"Job not found: {exc!s}") from exc
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        await logger.aexception(f"Unexpected error processing flow events for job {job_id}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc!s}") from exc


async def create_flow_response(
    queue: asyncio.Queue,
    event_manager: EventManager,
    event_task: asyncio.Task | None,
    *,
    queue_service: JobQueueService | None = None,
    job_id: str | None = None,
) -> DisconnectHandlerStreamingResponse:
    """Create a streaming response for the flow build process.

    When *queue_service* and *job_id* are provided and the service exposes a
    ``signal_cancel`` method (RedisJobQueueService with cancel_channel_enabled),
    a client disconnect on a non-owner worker (``event_task is None``) publishes
    a cross-worker cancel so the producer worker stops emitting events promptly
    instead of running the build to natural completion.
    """
    # Interval at which the heartbeat task refreshes the polling-watchdog
    # activity key while the streaming response is open. The heartbeat is
    # INDEPENDENT of the event yield cadence so a quiet build (long graph
    # step, slow LLM, no tokens for a while) keeps proving its client is
    # alive and does not get reclaimed by the watchdog. Read from the module
    # constant at call time so tests can monkeypatch it down.
    streaming_activity_refresh_s = STREAMING_ACTIVITY_REFRESH_S
    touch = getattr(queue_service, "touch_activity", None) if queue_service is not None and job_id is not None else None

    async def _heartbeat() -> None:
        # Strong reference is the local variable `heartbeat_task` below; this
        # closure also keeps `touch` and `job_id` alive for the task's lifetime.
        while True:
            try:
                await asyncio.sleep(streaming_activity_refresh_s)
            except asyncio.CancelledError:
                return
            try:
                await touch(job_id)  # type: ignore[misc]  # guarded by `if touch is not None` at task creation
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001
                # touch_activity already counts errors; a heartbeat hiccup must
                # not crash the streaming response. Debug-log and continue.
                await logger.adebug(f"streaming heartbeat: touch_activity failed for {job_id}: {exc}")

    heartbeat_task: asyncio.Task | None = (
        asyncio.create_task(_heartbeat(), name=f"stream-heartbeat-{job_id}") if touch is not None else None
    )

    def _cancel_heartbeat() -> None:
        if heartbeat_task is not None and not heartbeat_task.done():
            heartbeat_task.cancel()

    async def consume_and_yield() -> AsyncIterator[str]:
        try:
            while True:
                try:
                    event_id, value, put_time = await queue.get()
                    if value is None:
                        break
                    get_time = time.time()
                    yield value.decode("utf-8")
                    await logger.adebug(f"Event {event_id} consumed in {get_time - put_time:.4f}s")
                except Exception as exc:  # noqa: BLE001
                    await logger.aexception(f"Error consuming event: {exc}")
                    break
        finally:
            # Natural stream end (sentinel reached) → stop heartbeating.
            _cancel_heartbeat()

    async def on_disconnect() -> None:
        logger.debug("Client disconnected, closing tasks")
        _cancel_heartbeat()
        if event_task is not None:
            event_task.cancel()
        elif queue_service is not None and job_id is not None:
            # Cross-worker passive disconnect: publish a cancel signal so the
            # owning worker stops emitting events instead of running to natural
            # completion. signal_cancel is a no-op when the side-channel is
            # disabled or the backend is the in-memory queue.
            signal = getattr(queue_service, "signal_cancel", None)
            if signal is not None:
                try:
                    await signal(job_id)
                except Exception as exc:  # noqa: BLE001
                    await logger.awarning(f"Cross-worker disconnect: signal_cancel for {job_id} failed: {exc}")
        queue_cancel = getattr(queue, "cancel", None)
        if queue_cancel is not None:
            maybe_coro = queue_cancel()
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
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
    source_flow_id: uuid.UUID | None = None,
    job_id: uuid.UUID | str | None = None,
    resume: dict | None = None,
    run_id: str | None = None,
    track_job_status: bool = True,
    tweaks: dict | None = None,
) -> None:
    """Generate events for flow building process.

    This function handles the core flow building logic and generates appropriate events:
    - Building and validating the graph
    - Processing vertices
    - Handling errors and cleanup

    When ``run_id`` is provided the graph adopts it instead of minting a fresh
    one, so callers (e.g. background jobs) can later look up the run's vertex
    builds by that id. Defaults to a fresh uuid for the live build path.
    """
    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    if not inputs:
        inputs = InputValueRequest(session=str(flow_id))

    async def build_resumed_graph_and_get_order() -> tuple[list[str], list[str], Graph]:
        """Resume a suspended HITL run from its durable checkpoint instead of building fresh.

        Hydrates the graph, injects the human decision keyed by request_id, and un-builds
        the paused node so it re-runs and routes (its first-run output was a placeholder).
        """
        from lfx.graph.graph.base import Graph as LfxGraph
        from lfx.services.deps import get_checkpoint_service

        from langflow.api.v2.hitl import reroute_decision_on_timeout

        run_id = str(job_id)
        store = get_checkpoint_service()
        checkpoint = await store.load_by_run_id(run_id)
        if checkpoint is None:
            # Why: re-dispatching here (resume/job_id still set) recurses to RecursionError; a missing
            # or expired checkpoint is unrecoverable, so surface a clean 404 instead.
            raise HTTPException(status_code=404, detail="Checkpoint expired or not found; cannot resume this run.")
        graph = LfxGraph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
        pending = await get_job_service().get_pending_human_request(job_id)
        decision = reroute_decision_on_timeout(pending, resume["decision"])
        graph.human_input_decisions = {resume["request_id"]: decision}
        for vertex in graph.vertices:
            if f"{vertex.id}:{run_id}" == resume["request_id"]:
                vertex.built = False
                _rerun_non_input_predecessors(graph, vertex.id)
        first_layer = graph.resume_first_layer()
        for vertex_id in first_layer:
            graph.run_manager.add_to_vertices_being_run(vertex_id)
        await chat_service.set_cache(str(flow_id), graph)
        return first_layer, list(graph.vertices_to_run), graph

    async def build_graph_and_get_order() -> tuple[list[str], list[str], Graph]:
        if resume is not None and job_id is not None:
            return await build_resumed_graph_and_get_order()
        start_time = time.perf_counter()
        components_count = 0
        graph = None
        # The durable HITL path keys the checkpoint by job_id, so run_id MUST equal job_id when set;
        # otherwise honor an explicit run_id (background path) or mint a fresh uuid (foreground).
        build_run_id = str(job_id) if job_id is not None else (run_id or str(uuid.uuid4()))
        try:
            flow_id_str = str(flow_id)
            # Create a fresh session for database operations
            async with session_scope() as fresh_session:
                graph = await create_graph(fresh_session, flow_id_str, flow_name)

            # Apply request tweaks to the built graph. The sync path applies tweaks before Graph
            # construction; the streaming/background path builds from the DB (or request data), so
            # tweaks must be applied here or they are silently dropped. ``update_raw_params`` is used
            # rather than the lfx ``process_tweaks_on_graph`` helper because that helper only sets
            # ``vertex.params`` and does not persist the override to runtime.
            if tweaks:
                for vertex in graph.vertices:
                    if not (isinstance(vertex, Vertex) and isinstance(vertex.id, str)):
                        continue
                    if node_tweaks := tweaks.get(vertex.id):
                        node_tweaks = {k: v for k, v in node_tweaks.items() if k != "code"}
                        vertex.update_raw_params(node_tweaks, overwrite=True)

            graph.set_run_id(build_run_id)
            if job_id is not None:
                from lfx.services.deps import get_checkpoint_service

                graph.job_id = str(job_id)  # the checkpoint is keyed by job_id
                graph.checkpointing_enabled = True  # arm the pause seam for producers
                graph.checkpoint_store = get_checkpoint_service()
            first_layer = sort_vertices(graph)

            for vertex_id in first_layer:
                graph.run_manager.add_to_vertices_being_run(vertex_id)

            # Now vertices is a list of lists
            # We need to get the id of each vertex
            # and return the same structure but only with the ids
            components_count = len(graph.vertices)
            vertices_to_run = list(graph.vertices_to_run.union(get_top_level_vertices(graph, graph.vertices_to_run)))

            await chat_service.set_cache(flow_id_str, graph)
            await log_telemetry(start_time, components_count, run_id=build_run_id, success=True)

        except Exception as exc:
            await log_telemetry(
                start_time,
                components_count,
                run_id=build_run_id,
                success=False,
                error_message=str(exc),
            )

            if "stream or streaming set to True" in str(exc):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            await logger.aexception("Error checking build status: " + str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return first_layer, vertices_to_run, graph

    async def log_telemetry(
        start_time: float,
        components_count: int,
        *,
        run_id: str | None = None,
        success: bool,
        error_message: str | None = None,
    ):
        background_tasks.add_task(
            telemetry_service.log_package_playground,
            PlaygroundPayload(
                playground_seconds=int(time.perf_counter() - start_time),
                playground_component_count=components_count,
                playground_success=success,
                playground_error_message=str(error_message) if error_message else "",
                playground_run_id=run_id,
            ),
        )

    async def create_graph(fresh_session, flow_id_str: str, flow_name: str | None) -> Graph:
        if inputs is not None and getattr(inputs, "session", None) is not None:
            effective_session_id = inputs.session
        else:
            effective_session_id = flow_id_str

        if not data:
            # For public flows, source_flow_id is the real DB ID, flow_id is virtual.
            # Load from DB using the real ID, then override graph.flow_id with virtual.
            db_flow_id = source_flow_id if source_flow_id is not None else flow_id
            graph = await build_graph_from_db(
                flow_id=db_flow_id,
                session=fresh_session,
                chat_service=chat_service,
                user_id=str(current_user.id),
                session_id=effective_session_id,
            )
            if source_flow_id is not None:
                graph.flow_id = str(flow_id)
            return graph

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
            except GraphPausedException:
                # A pause is control flow, not a failure: converting it to an
                # error output would terminalize a suspendable run.
                raise
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, ComponentBuildError):
                    params = exc.message
                    tb = exc.formatted_traceback
                else:
                    tb = traceback.format_exc()
                    await logger.aexception("Error building Component")
                    params = format_exception_message(exc)
                message = {"errorMessage": params, "stackTrace": tb}
                valid = False
                error_message = params
                output_label = vertex.outputs[0]["name"] if vertex.outputs else "output"
                outputs = {output_label: OutputValue(message=message, type="error")}
                result_data_response = ResultDataResponse(results={}, outputs=outputs)
                artifacts = {}
                background_tasks.add_task(graph.end_all_traces_in_context(error=exc))

            result_data_response.message = artifacts

            # Log the vertex build. Job-tracked runs (background workflows pass a
            # ``run_id``) persist every vertex, including streaming terminal outputs,
            # so GET-status reconstruction by job_id is complete. The live build
            # path (``run_id is None``) keeps the original "skip streaming vertices"
            # behavior unchanged.
            if log_builds and (run_id is not None or not vertex.will_stream):
                background_tasks.add_task(
                    log_vertex_build,
                    flow_id=flow_id_str,
                    vertex_id=vertex_id,
                    valid=valid,
                    params=params,
                    data=result_data_response,
                    artifacts=artifacts,
                    # Key the persisted build by the run id so job-tracked runs can
                    # reconstruct status by job_id.
                    job_id=graph.run_id,
                )
            else:
                await chat_service.set_cache(flow_id_str, graph)

            timedelta = time.perf_counter() - start_time

            duration = format_elapsed_time(timedelta)
            result_data_response.duration = duration
            result_data_response.timedelta = timedelta
            vertex.add_build_time(timedelta)
            # Capture both inactivated and conditionally excluded vertices
            inactivated_vertices = list(graph.inactivated_vertices.union(graph.conditionally_excluded_vertices))
            graph.reset_inactivated_vertices()
            graph.reset_activated_vertices()

            # Note: Do not reset conditionally_excluded_vertices each iteration
            # This is handled by the ConditionalRouter component

            # graph.stop_vertex tells us if the user asked
            # to stop the build of the graph at a certain vertex
            # if it is in next_vertices_ids, we need to remove other
            # vertices from next_vertices_ids
            if graph.stop_vertex and graph.stop_vertex in next_runnable_vertices:
                next_runnable_vertices = [graph.stop_vertex]

            if not graph.run_manager.vertices_being_run and not next_runnable_vertices:
                background_tasks.add_task(graph.end_all_traces_in_context())

            build_response = VertexBuildResponse(
                inactivated_vertices=list(set(inactivated_vertices)),
                next_vertices_ids=list(set(next_runnable_vertices)),
                top_level_vertices=list(set(top_level_vertices)),
                valid=valid,
                params=params,
                id=vertex.id,
                data=result_data_response,
            )

            # Extract and send component input telemetry (separate payload)
            _log_component_input_telemetry(vertex, vertex_id, graph.run_id, background_tasks, telemetry_service)

            # Send component execution telemetry
            background_tasks.add_task(
                telemetry_service.log_package_component,
                ComponentPayload(
                    component_name=vertex_id.split("-")[0],
                    component_id=vertex_id,
                    component_seconds=int(time.perf_counter() - start_time),
                    component_success=valid,
                    component_error_message=error_message,
                    component_run_id=graph.run_id,
                ),
            )
        except GraphPausedException:
            raise
        except Exception as exc:
            if "vertex" in locals():
                # Extract and send component input telemetry even on error (separate payload)
                _log_component_input_telemetry(vertex, vertex_id, graph.run_id, background_tasks, telemetry_service)

            # Send component execution telemetry (error case)
            background_tasks.add_task(
                telemetry_service.log_package_component,
                ComponentPayload(
                    component_name=vertex_id.split("-")[0],
                    component_id=vertex_id,
                    component_seconds=int(time.perf_counter() - start_time),
                    component_success=False,
                    component_error_message=str(exc),
                    component_run_id=graph.run_id,
                ),
            )
            await logger.aexception("Error building Component")
            message = parse_exception(exc)
            raise HTTPException(status_code=500, detail=message) from exc

        return build_response

    async def build_vertices(
        vertex_id: str,
        graph: Graph,
        event_manager: EventManager,
        vertex_timedeltas: list[float],
    ) -> None:
        """Build vertices and handle their events.

        Args:
            vertex_id: The ID of the vertex to build
            graph: The graph instance
            event_manager: Manager for handling events
            vertex_timedeltas: Shared list to accumulate each vertex's timedelta
        """
        # Why: the background path never enters Graph.process(), so the pause boundary must live in this driver.
        await graph.check_and_handle_pause()
        try:
            vertex_build_response: VertexBuildResponse = await _build_vertex(vertex_id, graph, event_manager)
        except asyncio.CancelledError:
            await logger.ainfo("Build cancelled")
            raise

        # Accumulate the vertex timedelta
        if vertex_build_response.data.timedelta is not None:
            vertex_timedeltas.append(vertex_build_response.data.timedelta)

        # send built event or error event
        try:
            vertex_build_response_json = vertex_build_response.model_dump_json()
            build_data = json.loads(vertex_build_response_json)
        except Exception as exc:
            msg = f"Error serializing vertex build response: {exc}"
            raise ValueError(msg) from exc

        event_manager.on_end_vertex(
            data={"build_data": build_data, "output_meta": _output_meta_for_vertex(graph, vertex_id)}
        )

        if vertex_build_response.valid and vertex_build_response.next_vertices_ids:
            tasks = []
            for next_vertex_id in vertex_build_response.next_vertices_ids:
                task = asyncio.create_task(
                    build_vertices(
                        next_vertex_id,
                        graph,
                        event_manager,
                        vertex_timedeltas,
                    )
                )
                tasks.append(task)
            await asyncio.gather(*tasks)

    try:
        ids, vertices_to_run, graph = await build_graph_and_get_order()
    except Exception as e:
        error_message = ErrorMessage(
            flow_id=flow_id,
            exception=e,
            session_id=inputs.session,
        )
        event_manager.on_error(data=error_message.data)
        raise

    # Create a WORKFLOW job record so memory-base on_flow_output can track this run.
    # Best-effort: failures here must never break the build path.
    _build_job_svc = None
    _build_run_id: uuid.UUID | None = None
    try:
        _build_run_id = uuid.UUID(graph.run_id) if graph.run_id else None
        if track_job_status and _build_run_id is not None:
            _build_job_svc = get_job_service()
            # Background path already created the job; re-creating it = UNIQUE violation.
            if await _build_job_svc.get_job_by_job_id(_build_run_id) is None:
                await _build_job_svc.create_job(
                    job_id=_build_run_id,
                    flow_id=flow_id,
                    user_id=current_user.id,
                    job_type=JobType.WORKFLOW,
                )
    except Exception:  # noqa: BLE001
        await logger.awarning(
            "Failed to create workflow job for /build — memory base tracking disabled for flow %s",
            flow_id,
            exc_info=True,
        )
        _build_job_svc = None

    event_manager.on_vertices_sorted(data={"ids": ids, "to_run": vertices_to_run})

    vertex_timedeltas: list[float] = []
    event_manager.on_build_start(data={})

    # Strong references for fire-and-forget cleanup tasks created outside the
    # FastAPI background_tasks queue (which is already drained by the time we
    # reach the cancel path below). Each task removes itself on completion.
    cleanup_tasks: set[asyncio.Task] = set()

    async def _run_vertex_build() -> None:
        tasks = []
        for vertex_id in ids:
            task = asyncio.create_task(build_vertices(vertex_id, graph, event_manager, vertex_timedeltas))
            tasks.append(task)
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            # background_tasks is already drained after the POST /build response
            # is sent; add_task() is silently dropped here. Use create_task()
            # so the trace cleanup runs independently of background_tasks lifecycle.
            cleanup_task = asyncio.create_task(graph.end_all_traces_in_context()())
            cleanup_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(cleanup_tasks.discard)
            raise
        except GraphPausedException:
            # Suspension must reach the runtime unwrapped — emitting on_error
            # here would terminalize the run in every client.
            raise
        except Exception as e:
            await logger.aerror(f"Error building vertices: {e}")
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

    try:
        runner_owns_status = job_id is not None  # background path: JobRunner already wraps execute_with_status
        if _build_job_svc and _build_run_id and not runner_owns_status:
            await _build_job_svc.execute_with_status(_build_run_id, _run_vertex_build)
        else:
            await _run_vertex_build()
    except GraphPausedException as exc:
        # Non-terminal: persist the card to history, emit the pause event, end without on_end.
        from langflow.api.v2.hitl import persist_human_input_card

        await persist_human_input_card(exc.data or {}, flow_id, graph.session_id or str(flow_id), job_id)
        # Why: persist spans that ran before the pause so the trace detail isn't empty (merge is idempotent on resume).
        try:
            await graph.end_all_traces()
        except Exception:  # noqa: BLE001
            await logger.awarning("Failed to flush partial trace on pause for flow %s", flow_id, exc_info=True)
        event_manager.send_event(event_type="human_input_required", data=exc.data or {})
        await event_manager.queue.put((None, None, time.time()))
        return

    build_duration = sum(vertex_timedeltas)
    event_manager.on_end(data={"build_duration": build_duration})
    await graph.end_all_traces()

    # Fire memory-base auto-capture hook — non-blocking background effect.
    # Must use fire_and_forget_task (not background_tasks.add_task) because
    # generate_flow_events runs as an asyncio task; by the time the flow
    # finishes, FastAPI has already drained the background_tasks queue and any
    # tasks added after that point are silently dropped.
    # Gated on ``track_job_status`` for the same reason as the job row above:
    # when a caller owns the run's lifecycle (the v2 durable background path
    # passes ``track_job_status=False`` and fires this hook itself with the
    # durable job_id), firing here too would double-capture the flow output.
    if track_job_status:
        try:
            _run_id_uuid = uuid.UUID(graph.run_id) if graph.run_id else None  # type-cast only; same run_id set on graph
            await get_task_service().fire_and_forget_task(
                get_memory_base_service().on_flow_output,
                flow_id=flow_id,
                session_id=graph.session_id or str(flow_id),
                job_id=_run_id_uuid,
            )
        except (RuntimeError, ValueError, OSError):
            await logger.awarning("Memory base hook scheduling failed for flow %s", flow_id, exc_info=True)

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
        # Cross-worker cancel: this worker doesn't own the build task. If the
        # queue service supports a cancel side-channel (RedisJobQueueService with
        # cancel_channel_enabled=True), publish there so the owning worker can
        # cancel locally. Falls back to a no-op for the in-memory queue or for
        # Redis with cancel_channel_enabled=False (signal_cancel exists but
        # short-circuits to 0 without setting the marker).
        signal = getattr(queue_service, "signal_cancel", None)
        cross_worker_available = getattr(queue_service, "cross_worker_cancel_enabled", False)
        if signal is not None and cross_worker_available:
            try:
                receivers = await signal(job_id)
            except Exception as exc:  # noqa: BLE001
                # Redis publish failed; the marker isn't reliable either. Surface
                # this so the client can retry rather than silently no-op.
                await logger.aerror(f"signal_cancel for {job_id} failed: {exc}")
                return False
            # A return of 0 is not a failure: the persistent marker key was also
            # set, so a worker that picks up the job later will still apply the
            # cancel during its start_job marker check.
            await logger.ainfo(f"Cross-worker cancel signaled for job_id {job_id} (reached {receivers} subscriber(s))")
            return True
        # No cross-worker cancel support (in-memory backend or Redis without
        # cancel_channel_enabled). Two possible races: the job already finished
        # and was cleaned up, or it is running on an unreachable worker. We
        # cannot distinguish them cheaply, so return False.
        await logger.awarning(
            f"No event task found for job_id {job_id}. "
            "Cross-worker cancel is not available; cancellation could not be confirmed."
        )
        return False

    if event_task.done():
        await logger.ainfo(f"Task for job_id {job_id} is already completed")
        return True  # Nothing to cancel is still a success

    # Store the task reference to check status after cleanup
    task_before_cleanup = event_task

    try:
        # Perform cancel using the queue service so backends can preserve any
        # backend-specific end-of-stream guarantees before resource cleanup.
        await queue_service.cancel_job(job_id)
    except asyncio.CancelledError:
        # Check if the task was actually cancelled
        if task_before_cleanup.cancelled():
            await logger.ainfo(f"Successfully cancelled flow build for job_id {job_id} (CancelledError caught)")
            return True
        # If the task wasn't cancelled, re-raise the exception
        await logger.aerror(f"CancelledError caught but task for job_id {job_id} was not cancelled")
        raise

    # If no exception was raised, verify that the task was actually cancelled
    # The task should be done (cancelled) after cleanup
    if task_before_cleanup.cancelled():
        await logger.ainfo(f"Successfully cancelled flow build for job_id {job_id}")
        return True

    # If we get here, the task wasn't cancelled properly
    await logger.aerror(f"Failed to cancel flow build for job_id {job_id}, task is still running")
    return False
