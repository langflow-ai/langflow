"""FastAPI router for A2A protocol endpoints.

Two routers are defined:
1. `a2a_router` — Public A2A protocol endpoints mounted at /a2a/{agent_slug}/
2. `a2a_config_router` — Internal admin endpoints for managing A2A config

The instance-level toggle LANGFLOW_A2A_ENABLED controls whether the public
A2A endpoints are active. When disabled, all public routes return 404.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from lfx.log.logger import logger
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.a2a.agent_card import generate_agent_card
from langflow.api.a2a.config import validate_a2a_slug
from langflow.api.a2a.db_task_manager import DatabaseTaskManager
from langflow.api.a2a.flow_adapter import translate_inbound, translate_outbound
from langflow.api.a2a.streaming import A2AStreamBridge
from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow

# Module-level task manager. DB-backed so task state survives restarts and
# is shared across workers.
_task_manager = DatabaseTaskManager()

# Strong references to in-flight streaming background tasks so they are not
# garbage-collected while the SSE response is still being produced.
_background_tasks: set[asyncio.Task] = set()

# ---------------------------------------------------------------------------
# Pydantic models for request/response
# ---------------------------------------------------------------------------


class A2AConfigUpdate(BaseModel):
    """Request body for updating A2A config on a flow."""

    a2a_enabled: bool | None = None
    a2a_agent_slug: str | None = None
    a2a_name: str | None = None
    a2a_description: str | None = None


class A2AConfigRead(BaseModel):
    """Response body for reading A2A config."""

    a2a_enabled: bool
    a2a_agent_slug: str | None
    a2a_name: str | None
    a2a_description: str | None
    a2a_input_mode: str
    a2a_output_mode: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _a2a_is_enabled() -> bool:
    """Check the instance-level LANGFLOW_A2A_ENABLED toggle."""
    return os.environ.get("LANGFLOW_A2A_ENABLED", "true").lower() in ("true", "1", "yes")


async def _get_flow_by_slug(session, slug: str) -> Flow | None:
    """Look up a flow by its a2a_agent_slug."""
    stmt = select(Flow).where(
        Flow.a2a_agent_slug == slug,
        Flow.a2a_enabled == True,  # noqa: E712
    )
    result = await session.exec(stmt)
    return result.first()


def _validate_inbound_message(message: Any) -> None:
    """Reject A2A message bodies that carry no usable content.

    An A2A ``message:send``/``message:stream`` body must contain a ``message``
    with at least one part holding non-empty text or non-empty data. Empty,
    missing, or content-less bodies are rejected up front with 422 rather than
    executing the flow on empty input — which produces no meaningful artifact
    and is a client error, not a flow failure.
    """
    parts = message.get("parts") if isinstance(message, dict) else None
    if not isinstance(parts, list) or not parts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A2A message must include at least one part",
        )
    has_content = any(
        isinstance(part, dict)
        and ((part.get("kind") == "text" and part.get("text")) or (part.get("kind") == "data" and part.get("data")))
        for part in parts
    )
    if not has_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A2A message parts must contain non-empty text or data",
        )


# ---------------------------------------------------------------------------
# Public A2A protocol router
# ---------------------------------------------------------------------------

a2a_router = APIRouter(tags=["a2a"])


@a2a_router.get("/a2a/{agent_slug}/.well-known/agent-card.json")
async def get_agent_card(
    agent_slug: str,
    session: DbSession,
):
    """Serve the public AgentCard for an A2A-enabled flow.

    This endpoint does NOT require authentication — it's how external
    agents discover what this agent can do. The A2A spec defines this
    as a publicly accessible discovery endpoint.

    Returns 404 if:
    - LANGFLOW_A2A_ENABLED is false (instance-level kill switch)
    - No flow exists with this slug
    - The flow has a2a_enabled=False
    """
    if not _a2a_is_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A2A is not enabled")

    flow = await _get_flow_by_slug(session, agent_slug)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    base_url = f"/a2a/{agent_slug}"
    return generate_agent_card(flow, base_url=base_url)


@a2a_router.get("/a2a/{agent_slug}/v1/card")
async def get_extended_agent_card(
    agent_slug: str,
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001
):
    """Serve the extended AgentCard (auth-gated).

    Contains full skill schemas and detailed capability info.
    Requires authentication.
    """
    if not _a2a_is_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A2A is not enabled")

    flow = await _get_flow_by_slug(session, agent_slug)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    base_url = f"/a2a/{agent_slug}"
    card = generate_agent_card(flow, base_url=base_url)
    # Extended card can include additional details in the future
    card["extended"] = True
    return card


# ---------------------------------------------------------------------------
# message:send endpoint
# ---------------------------------------------------------------------------


@a2a_router.post("/a2a/{agent_slug}/v1/message:send")
async def message_send(
    agent_slug: str,
    body: dict[str, Any],
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Send an A2A message to a Langflow agent (synchronous).

    Executes the flow and returns a completed/failed Task.

    The request body follows the A2A protocol:
    {
        "message": { "role": "user", "parts": [...], "contextId": "..." },
        "taskId": "optional-for-retry"
    }
    """
    if not _a2a_is_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A2A is not enabled")

    flow = await _get_flow_by_slug(session, agent_slug)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    message = body.get("message", {})
    _validate_inbound_message(message)
    requested_task_id = body.get("taskId")
    context_id = message.get("contextId") or str(uuid.uuid4())

    # Check for INPUT_REQUIRED follow-up: if the client sends a message
    # with a taskId that's in INPUT_REQUIRED state, start a new execution
    # with the follow-up text (same session for conversation continuity).
    if requested_task_id and await _task_manager.is_input_required(requested_task_id):
        await _task_manager.resolve_input(requested_task_id)
        # Fall through to create a new task and execute — the same
        # contextId means the same session_id, so the Agent sees
        # prior conversation history including the question it asked.

    # Idempotent retry check (skip if we just resolved an input-required)
    elif requested_task_id:
        existing = await _task_manager.handle_retry(requested_task_id)
        if existing is not None:
            return existing

    # Create task
    task = await _task_manager.create_task(
        flow_id=str(flow.id),
        context_id=context_id,
        task_id=requested_task_id,
    )
    task_id = task["id"]

    try:
        # Translate A2A message → Langflow inputs
        flow_secret = str(flow.id)  # Use flow ID as HMAC secret for v1
        flow_inputs = await translate_inbound(message, flow_secret=flow_secret)

        # Update to WORKING
        await _task_manager.update_state(task_id, "working")

        # Execute the flow with A2A context so Agent components
        # can detect A2A execution and inject request_input tool
        a2a_context = {
            "task_id": task_id,
            "context_id": context_id,
            "task_manager": _task_manager,
        }
        result = await _execute_flow(flow, flow_inputs, session, user=current_user, a2a_context=a2a_context)

        # Translate outputs → A2A artifacts
        artifacts = await translate_outbound(result.outputs or [])

        # Check if the flow signaled input-required (via request_input tool
        # or a RequestInput component). The task_manager tracks this.
        if await _task_manager.is_input_required(task_id):
            task = await _task_manager.get_task(task_id)
            task["contextId"] = context_id
            task["artifacts"] = artifacts
            return task

        # Update to COMPLETED
        task = await _task_manager.update_state(task_id, "completed", artifacts=artifacts)
        task["contextId"] = context_id
        return task  # noqa: TRY300

    # Any flow execution error is converted into a FAILED task so the A2A
    # client always receives a well-formed Task rather than an HTTP 500.
    except Exception as e:  # noqa: BLE001
        logger.exception(f"A2A flow execution failed for task {task_id}: {e}")
        task = await _task_manager.update_state(task_id, "failed", error=str(e))
        task["contextId"] = context_id
        return task


async def _execute_flow(
    flow: Flow,
    flow_inputs: dict,
    session,  # noqa: ARG001
    *,
    user: Any,
    a2a_context: dict | None = None,
    stream: bool = False,
    event_manager: Any = None,
) -> Any:
    """Execute a Langflow flow with the given inputs.

    Wraps simple_run_flow() with the right parameters.

    Args:
        flow: The Flow model to execute.
        flow_inputs: Translated inputs from the A2A message.
        session: DB session (unused, kept for interface compatibility).
        user: The authenticated A2A caller. Forwarded as ``api_key_user``
              so flow execution runs with proper ownership (global
              variables, job records, permissions). Without it,
              ``simple_run_flow`` rejects the run with 401.
        a2a_context: Optional A2A execution context passed through to
                     the graph. Components can read this via self.ctx
                     to detect A2A execution and inject tools like
                     request_input.
        stream: When True, run in streaming mode and emit events to
                ``event_manager`` (used by message:stream).
        event_manager: EventManager that receives token/vertex/end
                       events when ``stream`` is True.
    """
    from langflow.api.v1.endpoints import simple_run_flow
    from langflow.api.v1.schemas import SimplifiedAPIRequest

    input_request = SimplifiedAPIRequest(
        input_value=flow_inputs["input_value"],
        input_type=flow_inputs.get("input_type", "chat"),
        output_type=flow_inputs.get("output_type", "chat"),
        tweaks=flow_inputs.get("tweaks"),
        session_id=flow_inputs.get("session_id"),
    )

    # Pass A2A context through to the graph so components (especially
    # Agent) can detect A2A execution and inject the request_input tool.
    context = None
    if a2a_context:
        context = {"a2a": a2a_context}

    return await simple_run_flow(
        flow=flow,
        input_request=input_request,
        stream=stream,
        api_key_user=user,
        event_manager=event_manager,
        context=context,
    )


# ---------------------------------------------------------------------------
# message:stream endpoint
# ---------------------------------------------------------------------------


@a2a_router.post("/a2a/{agent_slug}/v1/message:stream")
async def message_stream(
    agent_slug: str,
    body: dict[str, Any],
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Send an A2A message and receive a streaming SSE response.

    Returns a StreamingResponse with A2A-formatted SSE events:
    - TaskStatusUpdateEvent (working, completed, failed)
    - TaskArtifactUpdateEvent (partial text tokens)

    The flow executes in a background task while events are streamed
    to the client in real time.
    """
    if not _a2a_is_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A2A is not enabled")

    flow = await _get_flow_by_slug(session, agent_slug)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    message = body.get("message", {})
    _validate_inbound_message(message)
    context_id = message.get("contextId") or str(uuid.uuid4())
    flow_secret = str(flow.id)

    # Create task
    task = await _task_manager.create_task(
        flow_id=str(flow.id),
        context_id=context_id,
    )
    task_id = task["id"]

    # Create the stream bridge
    bridge = A2AStreamBridge(task_id=task_id, context_id=context_id)

    async def _run_and_stream():
        """Background: execute flow and feed events to bridge.

        Passes A2A context through to the graph so Agent components
        can inject the request_input tool. If the agent calls
        request_input during execution, this function emits
        INPUT_REQUIRED events to the stream and waits for resolution.
        """
        try:
            flow_inputs = await translate_inbound(message, flow_secret=flow_secret)
            await _task_manager.update_state(task_id, "working")

            # Emit initial WORKING status
            working_event = {
                "kind": "status-update",
                "taskId": task_id,
                "contextId": context_id,
                "status": {"state": "working"},
                "final": False,
            }
            await bridge.output_queue.put(working_event)

            # Pass A2A context and stream bridge so Agent can use
            # request_input tool and events flow to the SSE stream
            a2a_context = {
                "task_id": task_id,
                "context_id": context_id,
                "task_manager": _task_manager,
                "stream_bridge": bridge,
            }

            # Stream real execution events into the bridge as they happen:
            # LLM tokens (artifact-update, append) and per-vertex progress
            # (working status). The terminal state and the authoritative final
            # artifact are emitted explicitly below.
            from langflow.events.event_manager import create_stream_tokens_event_manager

            langflow_queue: asyncio.Queue = asyncio.Queue()
            event_manager = create_stream_tokens_event_manager(queue=langflow_queue)

            async def _forward_progress_events() -> None:
                while True:
                    item = await langflow_queue.get()
                    if item is None or item[1] is None:
                        break
                    raw = item[1]
                    raw_str = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                    try:
                        parsed = json.loads(raw_str.strip())
                    except (json.JSONDecodeError, AttributeError):
                        continue
                    # Only forward progress events; terminal state is emitted explicitly.
                    if parsed.get("event") in ("token", "end_vertex"):
                        await bridge.process_langflow_event(raw_str)

            forward_task = asyncio.create_task(_forward_progress_events())
            try:
                result = await _execute_flow(
                    flow,
                    flow_inputs,
                    session,
                    user=current_user,
                    a2a_context=a2a_context,
                    stream=True,
                    event_manager=event_manager,
                )
            finally:
                # Stop the forwarder and let it drain any remaining events.
                await langflow_queue.put(None)
                await forward_task

            # Check if the task entered INPUT_REQUIRED during execution
            # (this would be set by the request_input tool handler)
            current_task = await _task_manager.get_task(task_id)
            if current_task and current_task["status"]["state"] == "input-required":
                # Emit INPUT_REQUIRED event to the stream
                input_required_event = {
                    "kind": "status-update",
                    "taskId": task_id,
                    "contextId": context_id,
                    "status": current_task["status"],
                    "final": False,
                }
                await bridge.output_queue.put(input_required_event)
                # NOTE: The stream stays open. The client sends a follow-up
                # via message:send which resolves the pending input.
                # The request_input handler is awaiting an asyncio.Event
                # inside simple_run_flow, so when resolved, execution
                # continues and we'll get the result.

            # Translate and emit artifacts
            artifacts = await translate_outbound(result.outputs or [])
            for artifact in artifacts:
                artifact_event = {
                    "kind": "artifact-update",
                    "taskId": task_id,
                    "contextId": context_id,
                    "artifact": artifact,
                    "append": False,
                    "lastChunk": True,
                }
                await bridge.output_queue.put(artifact_event)

            # Emit COMPLETED
            await _task_manager.update_state(task_id, "completed", artifacts=artifacts)
            completed_event = {
                "kind": "status-update",
                "taskId": task_id,
                "contextId": context_id,
                "status": {"state": "completed"},
                "final": True,
            }
            await bridge.output_queue.put(completed_event)

        except Exception as e:  # noqa: BLE001 - surface any failure as a FAILED SSE event
            logger.exception(f"A2A streaming flow execution failed: {e}")
            await _task_manager.update_state(task_id, "failed", error=str(e))
            failed_event = {
                "kind": "status-update",
                "taskId": task_id,
                "contextId": context_id,
                "status": {
                    "state": "failed",
                    "message": {
                        "role": "agent",
                        "parts": [{"kind": "text", "text": str(e)}],
                    },
                },
                "final": True,
            }
            await bridge.output_queue.put(failed_event)

        finally:
            await bridge.finish()

    async def _event_generator():
        """Yield SSE-formatted events from the bridge output queue."""
        while True:
            event = await bridge.output_queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    # Start flow execution in background. Keep a strong reference so the
    # task isn't garbage-collected mid-stream (RUF006).
    stream_task = asyncio.create_task(_run_and_stream())
    _background_tasks.add(stream_task)
    stream_task.add_done_callback(_background_tasks.discard)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Task endpoints
# ---------------------------------------------------------------------------


def _task_belongs_to_flow(task: dict | None, flow: Flow) -> bool:
    """Whether a task was created by the given flow (agent).

    Tasks are scoped to their owning agent so one agent's task endpoints
    cannot read or mutate another agent's tasks.
    """
    if task is None:
        return False
    return (task.get("metadata") or {}).get("flowId") == str(flow.id)


@a2a_router.get("/a2a/{agent_slug}/v1/tasks/{task_id}")
async def get_task(
    agent_slug: str,
    task_id: str,
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001
):
    """Get the current state of an A2A task.

    Used for polling when the client doesn't have an SSE connection.
    Scoped to the agent identified by ``agent_slug``.
    """
    if not _a2a_is_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A2A is not enabled")
    flow = await _get_flow_by_slug(session, agent_slug)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    task = await _task_manager.get_task(task_id)
    if not _task_belongs_to_flow(task, flow):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@a2a_router.get("/a2a/{agent_slug}/v1/tasks")
async def list_tasks(
    agent_slug: str,
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001
    contextId: Annotated[str | None, Query()] = None,  # noqa: N803
):
    """List A2A tasks for this agent, optionally filtered by contextId."""
    if not _a2a_is_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A2A is not enabled")
    flow = await _get_flow_by_slug(session, agent_slug)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return await _task_manager.list_tasks(context_id=contextId, flow_id=str(flow.id))


@a2a_router.post("/a2a/{agent_slug}/v1/tasks/{task_id}:cancel")
async def cancel_task(
    agent_slug: str,
    task_id: str,
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001
):
    """Cancel an A2A task (best-effort). Scoped to the agent."""
    if not _a2a_is_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A2A is not enabled")
    flow = await _get_flow_by_slug(session, agent_slug)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    task = await _task_manager.get_task(task_id)
    if not _task_belongs_to_flow(task, flow):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    try:
        updated = await _task_manager.update_state(task_id, "canceled")
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")  # noqa: B904
    return updated


# ---------------------------------------------------------------------------
# Internal A2A config router (mounted under /api/v1/)
# ---------------------------------------------------------------------------

a2a_config_router = APIRouter(prefix="/flows", tags=["a2a-config"])


@a2a_config_router.put("/{flow_id}/a2a-config")
async def update_a2a_config(
    flow_id: UUID,
    config: A2AConfigUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Enable or update A2A configuration on a flow.

    Validates:
    - The flow exists and belongs to the current user
    - The slug format is valid
    - The slug is unique (no other flow uses it)
    - The flow is eligible for A2A (has Agent/LLM components)
    """
    # Load the flow
    flow = await session.get(Flow, flow_id)
    if not flow or flow.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    # Validate slug if provided
    if config.a2a_agent_slug is not None:
        try:
            validate_a2a_slug(config.a2a_agent_slug)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e

        # Check slug uniqueness
        existing = await session.exec(
            select(Flow).where(
                Flow.a2a_agent_slug == config.a2a_agent_slug,
                Flow.id != flow_id,
            )
        )
        if existing.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Agent slug '{config.a2a_agent_slug}' is already in use by another flow.",
            )

    # Apply updates
    if config.a2a_enabled is not None:
        flow.a2a_enabled = config.a2a_enabled
    if config.a2a_agent_slug is not None:
        flow.a2a_agent_slug = config.a2a_agent_slug
    if config.a2a_name is not None:
        flow.a2a_name = config.a2a_name
    if config.a2a_description is not None:
        flow.a2a_description = config.a2a_description

    session.add(flow)
    await session.flush()
    await session.refresh(flow)

    return A2AConfigRead(
        a2a_enabled=flow.a2a_enabled or False,
        a2a_agent_slug=flow.a2a_agent_slug,
        a2a_name=flow.a2a_name,
        a2a_description=flow.a2a_description,
        a2a_input_mode=getattr(flow, "a2a_input_mode", "chat"),
        a2a_output_mode=getattr(flow, "a2a_output_mode", "text"),
    )


@a2a_config_router.get("/{flow_id}/a2a-config")
async def get_a2a_config(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Read the A2A configuration for a flow."""
    flow = await session.get(Flow, flow_id)
    if not flow or flow.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    return A2AConfigRead(
        a2a_enabled=flow.a2a_enabled or False,
        a2a_agent_slug=flow.a2a_agent_slug,
        a2a_name=flow.a2a_name,
        a2a_description=flow.a2a_description,
        a2a_input_mode=getattr(flow, "a2a_input_mode", "chat"),
        a2a_output_mode=getattr(flow, "a2a_output_mode", "text"),
    )
