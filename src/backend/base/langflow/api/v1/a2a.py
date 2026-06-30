"""A2A protocol routes.

Two public per-flow endpoints, both behind ``LANGFLOW_A2A_ENABLED`` (default off):

- ``GET  /api/v1/a2a/{flow_id}/.well-known/agent-card.json`` serves the agent card.
- ``POST /api/v1/a2a/{flow_id}/jsonrpc`` serves the A2A JSON-RPC surface
  (``message/send`` runs the flow and returns a terminal Task; ``tasks/get``
  reads it back from the durable, DB-backed task store).

The router is mounted unconditionally and a per-request guard returns 404 when
the flag is off, so the routes are indistinguishable from "not mounted". This
mirrors the extensions router and avoids the import-time / env-file ordering
trap of reading a module-level flag.

The a2a-sdk server stack is protobuf-based. One shared ``DefaultRequestHandler``
+ ``DurableTaskStore`` + ``JsonRpcDispatcher`` serve every flow; the per-request
``flow_id`` is carried via the server call-context state into the protocol-pure
executor (``a2a_executor.FlowAgentExecutor``). Tasks persist in the ``a2a_tasks``
table so they survive restart and are visible across workers. Streaming is a
separate, later slice.
"""

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
from lfx.schema.workflow import WorkflowExecutionResponse, WorkflowRunRequest
from lfx.services.deps import get_settings_service, session_scope, session_scope_readonly
from lfx.workflow.converters import parse_workflow_run_request
from sqlmodel import select

from langflow.api.utils import DbSession
from langflow.api.v1.a2a_executor import FlowAgentExecutor
from langflow.api.v1.a2a_utils import build_agent_card
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.helpers.user import get_user_by_flow_id_or_endpoint_name
from langflow.services.database.models import A2ATask, Flow
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


class _FlowContextBuilder(DefaultServerCallContextBuilder):
    """Carry the per-request flow_id into the shared executor via call-context state."""

    def build(self, request: Request) -> ServerCallContext:
        context = super().build(request)
        context.state["flow_id"] = request.path_params["flow_id"]
        return context


async def _run_flow(flow_id: UUID, task_id: str, text: str) -> WorkflowExecutionResponse:
    """Run a flow synchronously through the v2 surface, as the flow owner.

    The public A2A endpoint carries no caller identity, so the run executes as
    the flow's owner. The helpers self-manage short readonly sessions, so no DB
    session is held across the up-to-300s run. ``task_id`` doubles as the v2
    job_id when it is a UUID (so run_id == taskId on the sync path); a non-UUID
    client task id falls back to a fresh job_id.
    """
    # Lazy import: langflow.api.v2.workflow pulls in the execution stack and this
    # module is imported during router assembly.
    from langflow.api.v2.workflow import execute_sync_workflow_with_timeout

    user = await get_user_by_flow_id_or_endpoint_name(str(flow_id))
    flow = await get_flow_by_id_or_endpoint_name(str(flow_id), user.id)
    parsed = parse_workflow_run_request(WorkflowRunRequest(flow_id=str(flow_id), input_value=text, mode="sync"))
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
    )


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
# selects the flow. agent_card is an empty proto card (only read on stream/push
# paths, which this slice doesn't mount); the real per-flow card is the GET route.
# DurableTaskStore does no DB work at construction, so the import-time singleton is safe.
_HANDLER = DefaultRequestHandler(
    agent_executor=FlowAgentExecutor(_run_flow),
    task_store=DurableTaskStore(),
    agent_card=pb.AgentCard(),
)
_DISPATCHER = JsonRpcDispatcher(
    request_handler=_HANDLER,
    context_builder=_FlowContextBuilder(),
    enable_v0_3_compat=True,  # routes the spec method names message/send and tasks/get
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
    """Serve the A2A JSON-RPC surface (message/send, tasks/get) for an agent flow.

    Public and gated like the card route; the flow runs as its owner. Returns the
    SDK's JSON-RPC response (HTTP 200 even for JSON-RPC-level errors). No
    ``DbSession`` dependency here: holding a session open across the run would
    fight the v2 surface's lock-avoidance design, and the gate/run resolve from
    flow_id via short self-managed sessions.
    """
    _require_a2a_enabled()

    # Public endpoint: gate on the flow itself (resolve by PK, owner-agnostic),
    # like the card route. _run_flow resolves the owner for the actual run.
    flow = await get_flow_by_id_or_endpoint_name(str(flow_id))
    if flow.flow_type != FlowType.AGENT or not flow.a2a_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    return await _DISPATCHER.handle_requests(request)
