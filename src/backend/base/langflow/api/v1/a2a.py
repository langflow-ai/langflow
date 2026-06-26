"""A2A protocol routes.

Two public per-flow endpoints, both behind ``LANGFLOW_A2A_ENABLED`` (default off):

- ``GET  /api/v1/a2a/{flow_id}/.well-known/agent-card.json`` serves the agent card.
- ``POST /api/v1/a2a/{flow_id}/jsonrpc`` serves the A2A JSON-RPC surface
  (``message/send`` runs the flow and returns a terminal Task; ``message/stream``
  streams the same run's lifecycle as SSE; ``tasks/get`` reads a task back from
  the durable, DB-backed store; ``tasks/resubscribe`` re-attaches to a live run).

The router is mounted unconditionally and a per-request guard returns 404 when
the flag is off, so the routes are indistinguishable from "not mounted". This
mirrors the extensions router and avoids the import-time / env-file ordering
trap of reading a module-level flag.

The a2a-sdk server stack is protobuf-based. One shared ``DefaultRequestHandler``
+ ``DurableTaskStore`` + ``JsonRpcDispatcher`` serve every flow; the per-request
``flow_id`` is carried via the server call-context state into the protocol-pure
executor (``a2a_executor.FlowAgentExecutor``). Tasks persist in the ``a2a_tasks``
table so they survive restart and are visible across workers.
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

from a2a.server.context import ServerCallContext
from a2a.server.owner_resolver import resolve_user_scope
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.common import DefaultServerCallContextBuilder
from a2a.server.routes.jsonrpc_dispatcher import JsonRpcDispatcher
from a2a.server.tasks import TaskStore
from a2a.types import a2a_pb2 as pb
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from google.protobuf.json_format import MessageToDict, ParseDict
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.checkpoint.store import CheckpointStore
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.base import Graph
from lfx.schema.workflow import (
    GLOBAL_KEY_MAX_LEN,
    JobStatus,
    WorkflowExecutionResponse,
    WorkflowRunRequest,
)
from lfx.services.deps import get_settings_service, session_scope, session_scope_readonly
from lfx.workflow.converters import parse_workflow_run_request, run_response_to_workflow_response
from sqlmodel import select

from langflow.api.utils import DbSession
from langflow.api.v1.a2a_executor import FlowAgentExecutor
from langflow.api.v1.a2a_utils import A2A_APIKEY_HEADER, build_agent_card, folder_auth_type
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.helpers.user import get_user_by_flow_id_or_endpoint_name
from langflow.services.database.models import A2ACheckpoint, A2ATask, Flow
from langflow.services.database.models.api_key.crud import check_key
from langflow.services.database.models.flow.model import FlowType

router = APIRouter(prefix="/a2a", tags=["a2a"])


def _require_a2a_enabled() -> None:
    """Return 404 when the A2A feature flag is off.

    Reads the live settings per request (after env/dotenv load), matching
    langflow.api.v1.extensions._require_extension_reload_enabled.
    """
    settings = get_settings_service().settings
    if not getattr(settings, "a2a_enabled", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


async def _enforce_a2a_auth(flow: Flow, request: Request) -> None:
    """Enforce the apikey scheme the card advertises, before any dispatch.

    When the flow's folder requires apikey auth, the request must carry a valid
    langflow API key in ``x-api-key`` whose owner is the flow owner. The flow always
    runs as its owner (see ``_run_flow``), so accepting another user's valid key would
    let them trigger a run under the owner's identity, so scope to ``flow.user_id``.

    Uses ``check_key`` directly, NOT ``api_key_security``: under AUTO_LOGIN the latter
    returns the superuser for a *missing* key, which would silently bypass this gate.
    ``"none"`` / missing / no-folder stay public; ``"oauth"`` stays public this slice
    (the card advertises no scheme for it, so a discovery client sends no key).
    """
    # Short writable session (check_key flushes usage counters), closed before
    # dispatch so no lock is held across the up-to-300s run.
    async with session_scope() as session:
        if await folder_auth_type(flow, session) != "apikey":
            return  # public agent
        api_key = request.headers.get(A2A_APIKEY_HEADER)
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
        user = await check_key(session, api_key)
        # Same message for invalid and wrong-owner: don't reveal a key is valid for another user.
        if user is None or user.id != flow.user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


class _FlowContextBuilder(DefaultServerCallContextBuilder):
    """Carry the per-request flow_id into the shared executor via call-context state."""

    def build(self, request: Request) -> ServerCallContext:
        context = super().build(request)
        context.state["flow_id"] = request.path_params["flow_id"]
        return context


async def _run_flow(flow_id: UUID, task_id: str, text: str, context_id: str | None) -> WorkflowExecutionResponse:
    """Run a flow synchronously through the v2 surface, as the flow owner.

    The public A2A endpoint carries no caller identity, so the run executes as
    the flow's owner. The helpers self-manage short readonly sessions, so no DB
    session is held across the up-to-300s run. ``task_id`` doubles as the v2
    job_id when it is a UUID (so run_id == taskId on the sync path); a non-UUID
    client task id falls back to a fresh job_id.

    The A2A ``context_id`` becomes the flow ``session_id`` so multi-turn calls
    sharing a contextId share chat memory. The SDK mints a contextId when the
    client omits one, so each conversation gets its own isolated session.
    """
    # Lazy import: langflow.api.v2.workflow pulls in the execution stack and this
    # module is imported during router assembly.
    from langflow.api.v2.workflow import execute_sync_workflow_with_timeout

    user = await get_user_by_flow_id_or_endpoint_name(str(flow_id))
    flow = await get_flow_by_id_or_endpoint_name(str(flow_id), user.id)
    # context_id is client-controlled on a public flow and lands in the indexed
    # MessageTable.session_id, so bound it like the public run schema does (Postgres
    # btree entries are size-capped, so an over-long value could fail the insert). An
    # over-bound id falls back to the per-flow default session; truncating instead
    # would collide two long ids into one conversation.
    session_id = context_id if context_id and len(context_id) <= GLOBAL_KEY_MAX_LEN else None
    parsed = parse_workflow_run_request(
        WorkflowRunRequest(flow_id=str(flow_id), input_value=text, mode="sync", session_id=session_id)
    )
    try:
        job_id = UUID(task_id)
    except ValueError:
        job_id = uuid4()
    return await execute_sync_workflow_with_timeout(
        parsed=parsed,
        flow=flow,
        job_id=job_id,
        current_user=user,
        background_tasks=BackgroundTasks(),
        http_request=None,
        # HITL: a flow with a HumanInput node durably checkpoints and returns a suspended
        # response instead of running through. Resume happens in _resume_flow.
        checkpoint_store=A2ACheckpointStore(),
    )


def _resolve_action(text: str, pending: dict[str, Any]) -> str | None:
    """The allowed HumanInput action id the reply selects, or None when it matches none.

    The node routes on an ``action_id`` (``label.lower().replace(" ", "_")``). Match the reply
    against the pause's allowed action ids, then against option labels. None means "no offered
    action", so the caller re-parks rather than taking an empty no-branch path.
    """
    allowed = pending.get("allowed_decisions") or []
    candidate = text.strip().lower().replace(" ", "_")
    if candidate in allowed:
        return candidate
    for option in pending.get("options") or []:
        if str(option.get("label", "")).strip().lower() == text.strip().lower():
            return option.get("action_id")
    return None


def _suspended_response(flow_id: UUID, task_id: str, session_id: str | None, pending: dict[str, Any]):
    return WorkflowExecutionResponse(
        flow_id=str(flow_id),
        session_id=session_id,
        job_id=task_id,
        status=JobStatus.SUSPENDED,
        human_request=pending,
    )


async def _resume_flow(flow_id: UUID, task_id: str, text: str) -> WorkflowExecutionResponse:
    """Resume a HITL run that paused for human input, advancing to the next pause or completion.

    The A2A task id is the run id, so the parked checkpoint is loaded by it. The follow-up
    message text becomes the HumanInput decision; the restored graph re-runs from the paused
    node and either completes (checkpoint cleared) or pauses again (a new checkpoint, another
    ``input-required``). Built on lfx checkpoint primitives so it is portable to lfx serve.

    A reply that matches no offered action re-parks the task (the human can answer again) rather
    than burning it on an empty completion. The checkpoint is dropped on completion or failure,
    but a never-answered task keeps its row (no background reaper on this path yet).
    """
    store = A2ACheckpointStore()
    checkpoint = await store.load_by_run_id(task_id)
    if checkpoint is None:
        # The parked run is unrecoverable (cleared/expired); surface a failed task.
        msg = f"No resumable checkpoint for A2A task {task_id}"
        raise RuntimeError(msg)
    # Defense in depth: a task parked under one flow must not be resumable via another flow's
    # endpoint (which would run a different owner's graph). Don't delete it on mismatch.
    if checkpoint.flow_id != str(flow_id):
        msg = f"A2A task {task_id} does not belong to flow {flow_id}"
        raise RuntimeError(msg)

    pending = (checkpoint.pause_context or {}).get("data") or {}
    allowed = pending.get("allowed_decisions") or []
    action_id = _resolve_action(text, pending)
    if allowed and action_id is None:
        # Out-of-range answer: re-park so the human can retry, keeping the checkpoint.
        return _suspended_response(flow_id, task_id, checkpoint.session_id, pending)

    decision = {"action_id": action_id or text.strip().lower().replace(" ", "_"), "values": {}}
    graph = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    request_id = pending.get("request_id")
    graph.human_input_decisions = {request_id: decision}
    # Un-build the paused node so it re-runs and reads the injected decision.
    for vertex in graph.vertices:
        if f"{vertex.id}:{graph.run_id}" == request_id:
            vertex.built = False

    from langflow.api.v2.workflow import EXECUTION_TIMEOUT
    from langflow.processing.process import run_graph_internal

    try:
        run_outputs, session_id = await asyncio.wait_for(
            run_graph_internal(
                graph,
                str(flow_id),
                session_id=graph.session_id,
                inputs=[],
                outputs=graph.get_terminal_nodes(),
            ),
            timeout=EXECUTION_TIMEOUT,
        )
    except GraphPausedException as exc:
        # Paused again (multi-step HITL): the new checkpoint is already saved under this run_id.
        return _suspended_response(flow_id, task_id, graph.session_id, exc.data or {})
    except Exception:
        # Failure/timeout: drop the now-unusable checkpoint so it doesn't orphan a terminal task.
        await store.delete_by_run_id(task_id)
        raise

    await store.delete_by_run_id(task_id)
    from langflow.api.v1.schemas import RunResponse

    run_response = RunResponse(outputs=run_outputs, session_id=session_id)
    return run_response_to_workflow_response(
        run_response=run_response,
        flow_id=str(flow_id),
        job_id=task_id,
        inputs={},
        graph=graph,
    )


class A2ACheckpointStore(CheckpointStore):
    """DB-backed graph checkpoint store for A2A HITL resume, keyed by ``run_id`` (the task id).

    The graph saves a checkpoint here when a HumanInput node pauses; resume reads it back by
    run id. ``GraphCheckpoint`` round-trips through JSON, so it lives in one ``a2a_checkpoints``
    row. Only ``save`` / ``load_by_run_id`` / ``delete_by_run_id`` are used; the id/session
    lookups would scan the table and aren't on any A2A path, so they raise. lfx-portable:
    ``session_scope`` + one SQLModel table, no langflow job machinery.
    """

    async def save(self, checkpoint: GraphCheckpoint) -> None:
        blob: dict[str, Any] = checkpoint.model_dump(mode="json")
        async with session_scope() as session:
            row = await session.get(A2ACheckpoint, checkpoint.run_id)
            if row is None:
                session.add(A2ACheckpoint(run_id=checkpoint.run_id, checkpoint=blob))
            else:
                row.checkpoint = blob  # fresh dict reference flags the JSON column dirty

    async def load_by_run_id(self, run_id: str) -> GraphCheckpoint | None:
        async with session_scope_readonly() as session:  # pure read, no commit
            row = await session.get(A2ACheckpoint, run_id)
            blob = row.checkpoint if row is not None else None
        return GraphCheckpoint.model_validate(blob) if blob is not None else None

    async def delete_by_run_id(self, run_id: str) -> None:
        async with session_scope() as session:
            row = await session.get(A2ACheckpoint, run_id)
            if row is not None:
                await session.delete(row)

    async def load(self, checkpoint_id: str) -> GraphCheckpoint | None:
        # A2A resolves by run_id (== task id); a by-checkpoint-id lookup isn't mounted.
        raise NotImplementedError

    async def delete(self, checkpoint_id: str) -> None:
        raise NotImplementedError

    async def list_by_session(self, session_id: str) -> list[GraphCheckpoint]:
        raise NotImplementedError


class DurableTaskStore(TaskStore):
    """DB-backed A2A task store keyed by ``(task_id, owner)``.

    One short session per op, so tasks survive a restart and are shared across workers
    (unlike the SDK in-memory store). Owner-scoped to match the SDK contract; ``owner``
    is '' on the anonymous public endpoint. The whole proto Task is stored as one JSON
    blob since the mounted surface only does point lookups by id.
    """

    async def save(self, task: pb.Task, context: ServerCallContext) -> None:
        owner = resolve_user_scope(context)
        blob: dict[str, Any] = MessageToDict(task)
        async with session_scope() as session:
            row = await session.get(A2ATask, (task.id, owner))
            if row is None:
                session.add(A2ATask(id=task.id, owner=owner, task=blob))
            else:
                row.task = blob  # fresh dict reference flags the JSON column dirty

    async def get(self, task_id: str, context: ServerCallContext) -> pb.Task | None:
        owner = resolve_user_scope(context)
        async with session_scope_readonly() as session:  # pure read, no commit
            row = await session.get(A2ATask, (task_id, owner))
            blob = row.task if row is not None else None
        if blob is None:
            return None
        task = pb.Task()
        ParseDict(blob, task)
        return task

    async def list(self, params: pb.ListTasksRequest, context: ServerCallContext) -> pb.ListTasksResponse:
        # ponytail: tasks/list isn't routed this slice; implement it (and decompose
        # context_id/status into columns) when F5/F7 mount a list/filter path.
        raise NotImplementedError

    async def delete(self, task_id: str, context: ServerCallContext) -> None:
        # ponytail: no mounted path calls delete this slice.
        raise NotImplementedError


# One shared handler/store/dispatcher serve every flow; the per-request flow_id
# selects the flow. The handler card carries only capabilities the SDK reads to
# gate methods: streaming=True lets the @validate guard admit message/stream and
# tasks/resubscribe. The real per-flow discovery card is the GET route.
# DurableTaskStore does no DB work at construction, so the import-time singleton is safe.
# ponytail: streaming emits the run's lifecycle events (submitted -> working ->
# artifact -> completed) as SSE; per-token deltas would inject a stream_flow callable
# into the executor. tasks/resubscribe is best-effort same-worker live re-attach (the
# default in-memory QueueManager); a terminal or cross-worker task returns a spec error
# and tasks/get covers terminal reads. Durable cross-worker re-attach is a later slice.
_HANDLER = DefaultRequestHandler(
    agent_executor=FlowAgentExecutor(_run_flow, _resume_flow),
    task_store=DurableTaskStore(),
    agent_card=pb.AgentCard(capabilities=pb.AgentCapabilities(streaming=True)),
)
_DISPATCHER = JsonRpcDispatcher(
    request_handler=_HANDLER,
    context_builder=_FlowContextBuilder(),
    enable_v0_3_compat=True,  # routes spec method names: message/send, message/stream, tasks/get, tasks/resubscribe
)


@router.get("/{flow_id}/.well-known/agent-card.json")
async def get_agent_card(flow_id: UUID, request: Request, session: DbSession) -> dict:
    """Serve the spec-valid A2A agent card for an agent-typed, a2a_enabled flow.

    Public by design: the A2A public agent card is unauthenticated by spec, so
    gating it behind login would break standard discovery. Returns 404 when the
    flag is off, the flow does not exist, the flow is not flow_type=agent, or
    a2a_enabled is falsy.
    """
    _require_a2a_enabled()

    flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
    if flow is None or flow.flow_type != FlowType.AGENT or not flow.a2a_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    rpc_url = str(request.base_url).rstrip("/") + f"/api/v1/a2a/{flow_id}/jsonrpc"
    return await build_agent_card(flow, rpc_url=rpc_url, session=session)


@router.post("/{flow_id}/jsonrpc")
async def a2a_jsonrpc(flow_id: UUID, request: Request) -> Response:
    """Serve the A2A JSON-RPC surface (message/send, message/stream, tasks/get, tasks/resubscribe) for an agent flow.

    Gated like the card route; apikey-folder flows additionally require a valid owner
    key (401). The flow runs as its owner. Returns the SDK's JSON-RPC response (HTTP 200
    even for JSON-RPC-level errors). No ``DbSession`` dependency here: holding a session
    open across the run would fight the v2 surface's lock-avoidance design, and the
    gate/run resolve from flow_id via short self-managed sessions.
    """
    _require_a2a_enabled()

    # Gate on the flow itself (resolve by PK, owner-agnostic), like the card route.
    # _run_flow resolves the owner for the actual run.
    flow = await get_flow_by_id_or_endpoint_name(str(flow_id))
    if flow.flow_type != FlowType.AGENT or not flow.a2a_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    # apikey-folder flows require a valid owner key here (401); "none" stays public.
    # Runs after the 404 gate, so disabled/non-agent/unknown flows never reach a 401.
    await _enforce_a2a_auth(flow, request)

    return await _DISPATCHER.handle_requests(request)
