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
import hashlib
from typing import Any
from uuid import UUID, uuid4

import httpx
from a2a.server.context import ServerCallContext
from a2a.server.owner_resolver import resolve_user_scope
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.common import DefaultServerCallContextBuilder
from a2a.server.routes.jsonrpc_dispatcher import JsonRpcDispatcher
from a2a.server.tasks import BasePushNotificationSender, InMemoryPushNotificationConfigStore, TaskStore
from a2a.types import a2a_pb2 as pb
from a2a.utils.errors import InvalidParamsError, TaskNotFoundError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from google.protobuf.json_format import MessageToDict, ParseDict
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.checkpoint.store import CheckpointStore
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.base import Graph
from lfx.log.logger import logger
from lfx.schema.workflow import (
    GLOBAL_KEY_MAX_LEN,
    JobStatus,
    WorkflowExecutionResponse,
    WorkflowRunRequest,
)
from lfx.services.deps import get_settings_service, session_scope, session_scope_readonly
from lfx.utils.ssrf_transport import create_ssrf_protected_client
from lfx.workflow.converters import parse_workflow_run_request, run_response_to_workflow_response
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.flow_utils import compute_virtual_flow_id, scope_session_to_namespace
from langflow.api.v1.a2a_executor import FlowAgentExecutor
from langflow.api.v1.a2a_utils import (
    A2A_APIKEY_HEADER,
    build_agent_card,
    folder_auth_type,
    validate_webhook_url,
    webhook_pin_host,
)
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
    """Enforce the folder's auth scheme before any dispatch, failing closed on the rest.

    The flow always runs as its owner (see ``_run_flow``), so an unauthenticated run is a
    run under the owner's identity. Gate by the folder's ``auth_type``:

    - ``"none"`` / missing / no-folder -> public agent (the intended public A2A model).
    - ``"apikey"`` / ``"oauth"`` -> require a valid langflow API key in ``x-api-key`` whose
      owner is the flow owner. An oauth folder is fronted by an external OAuth broker (the dance
      happens in front); the langflow transport itself still takes an owner-scoped api key,
      exactly as the MCP transport does (``mcp_projects.verify_project_auth``), since credential
      forwarding from the broker isn't available yet. Accepting another user's valid key would
      let them trigger a run under the owner's identity, so scope to ``flow.user_id``.
    - anything else (an auth type A2A doesn't understand) -> fail closed with 403: treating a
      *protected* folder as public would expose an owner-identity run anonymously.

    Uses ``check_key`` directly, NOT ``api_key_security``: under AUTO_LOGIN the latter
    returns the superuser for a *missing* key, which would silently bypass this gate.
    """
    # Short writable session (check_key flushes usage counters), closed before
    # dispatch so no lock is held across the up-to-300s run.
    async with session_scope() as session:
        auth_type = await folder_auth_type(flow, session)
        if auth_type == "none":
            return  # public agent
        if auth_type not in ("apikey", "oauth"):
            # Protected folder with a scheme A2A can't enforce: fail closed, never public.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"A2A access is disabled for this agent: unsupported folder auth type {auth_type!r}.",
            )
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

    The A2A ``context_id`` is namespaced under a per-(owner, flow) virtual id and
    that becomes the flow ``session_id``, so multi-turn calls sharing a contextId
    share chat memory while a contextId can never address another flow's session.
    The SDK mints a contextId when the client omits one, so each conversation gets
    its own isolated session.
    """
    # Lazy import: langflow.api.v2.workflow pulls in the execution stack and this
    # module is imported during router assembly.
    from langflow.api.v2.workflow import execute_sync_workflow_with_timeout

    user = await get_user_by_flow_id_or_endpoint_name(str(flow_id))
    flow = await get_flow_by_id_or_endpoint_name(str(flow_id), user.id)
    # context_id is client-controlled on a public endpoint, so namespace it under a
    # per-(owner, flow) virtual id before it becomes the chat session_id: a contextId
    # can never address another flow's session, and since the run always executes as the
    # flow owner (apikey-gated flows admit only the owner's key) the owner id folds the
    # principal into the key. The namespaced value lands in the indexed
    # MessageTable.session_id (Postgres btree entries are size-capped), so when the
    # composed key would exceed the bound, hash the contextId rather than truncating
    # (which would collide two long ids) or falling back to the shared per-flow default
    # (which would re-open the cross-caller leak). Only an absent contextId uses the default.
    namespace = str(compute_virtual_flow_id(user.id, flow_id))
    if context_id:
        scoped = scope_session_to_namespace(context_id, namespace)
        session_id = (
            scoped
            if scoped and len(scoped) <= GLOBAL_KEY_MAX_LEN
            else f"{namespace}:{hashlib.sha256(context_id.encode()).hexdigest()}"
        )
    else:
        session_id = None
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


def _push_config_scope(context: ServerCallContext) -> str:
    """Key push configs by (owner, flow) so flow B can't read/overwrite/delete flow A's.

    The endpoint is anonymous, so ``resolve_user_scope`` is the same '' for every flow;
    the per-request flow_id (carried in call-context state by ``_FlowContextBuilder``) is
    the real discriminator. Mirrors the flow-ownership defense in ``_resume_flow``. Only
    the user-callable set/get/list/delete paths are scoped; dispatch fans out by task_id
    via ``get_info_for_dispatch`` and is unaffected.
    """
    return f"{resolve_user_scope(context)}:{context.state.get('flow_id', '')}"


class _SafePushConfigStore(InMemoryPushNotificationConfigStore):
    """Push-notification config store that SSRF-guards the webhook URL at registration.

    The webhook target is caller-controlled on a public endpoint, so reject one that
    resolves to a private/loopback/link-local address before storing it (rather than
    letting the sender POST there). In-memory + per-worker for now; durable cross-worker
    push configs are a later slice (like the streaming queue manager).
    """

    async def set_info(self, task_id: str, notification_config: pb.TaskPushNotificationConfig, context) -> None:
        try:
            await validate_webhook_url(notification_config.url)
        except ValueError as exc:
            raise InvalidParamsError(message=str(exc)) from exc
        await super().set_info(task_id, notification_config, context)


class _SafePushNotificationSender(BasePushNotificationSender):
    """Re-validate + DNS-pin the webhook at dispatch, closing the registration-time rebind gap.

    ``_SafePushConfigStore`` validates at registration, but a host can re-resolve to a
    private/metadata IP afterwards (DNS rebinding). Re-resolve here and pin the connection
    to the just-validated IPs (via the shared SSRF transport) so a rebind can't land on an
    internal address. A webhook that now resolves to a blocked address is dropped (logged),
    matching the SDK's swallow-and-return-False on a failed send.
    """

    async def _dispatch_notification(self, event, push_info, task_id) -> bool:
        url = push_info.url
        try:
            validated_ips = await validate_webhook_url(url)
        except ValueError:
            logger.warning("A2A push webhook for task %s blocked by SSRF check: %s", task_id, url)
            return False
        # Pin by the exact host httpx connects to (IDNA/punycode raw_host) -- the same
        # derivation validate_webhook_url resolved -- so the pin key can't diverge from the
        # connected host for an IDN webhook (which would silently bypass the pin).
        hostname = webhook_pin_host(url)
        if not (validated_ips and hostname):
            # Private webhooks allowed / allowlisted host / protection off: nothing to pin.
            return await super()._dispatch_notification(event, push_info, task_id)
        # ponytail: per-dispatch client so DNS is pinned to the IPs just validated for this
        # host; reuse the SDK's exact POST (token header, error swallow) via a bound sender.
        async with create_ssrf_protected_client(
            hostname=hostname, validated_ips=validated_ips, timeout=_PUSH_TIMEOUT
        ) as client:
            pinned = BasePushNotificationSender(client, self._config_store)
            return await pinned._dispatch_notification(event, push_info, task_id)  # noqa: SLF001


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


def _is_terminal_cancel(blob: dict[str, Any] | None) -> bool:
    """True when a stored task blob is in the terminal CANCELED state (MessageToDict enum name)."""
    return bool(blob) and (blob.get("status") or {}).get("state") == "TASK_STATE_CANCELED"


def _task_scope(context: ServerCallContext) -> str:
    """Owner key for the durable task store, scoped to the flow.

    ``resolve_user_scope`` returns '' for every anonymous public caller, so without the flow it
    keys all public flows' tasks together and a caller could read or cancel another flow's task by
    id through a different flow's endpoint. Folding the path ``flow_id`` into the key makes such a
    cross-flow lookup miss. Falls back to the plain owner scope when no flow_id is on the context.

    Delimited by ':' like ``_push_config_scope``: the flow_id prefix is a UUID (no ':'), so the key
    is unambiguous, and it avoids a NUL byte that Postgres text columns reject at write time.
    """
    owner = resolve_user_scope(context)
    flow_id = (getattr(context, "state", None) or {}).get("flow_id")
    return f"{flow_id}:{owner}" if flow_id else owner


class DurableTaskStore(TaskStore):
    """DB-backed A2A task store keyed by ``(task_id, owner)``.

    One short session per op, so tasks survive a restart and are shared across workers
    (unlike the SDK in-memory store). Owner-scoped to match the SDK contract; ``owner``
    is '' on the anonymous public endpoint. The whole proto Task is stored as one JSON
    blob since the mounted surface only does point lookups by id.
    """

    async def save(self, task: pb.Task, context: ServerCallContext) -> None:
        owner = _task_scope(context)
        blob: dict[str, Any] = MessageToDict(task)
        async with session_scope() as session:
            # Lock the row so a completion racing a cancel can't read stale state and then clobber
            # the terminal CANCELED (Postgres row lock; a no-op on SQLite, which serializes writers).
            row = await session.get(A2ATask, (task.id, owner), with_for_update=True)
            if row is None:
                session.add(A2ATask(id=task.id, owner=owner, task=blob))
            elif _is_terminal_cancel(row.task) and not _is_terminal_cancel(blob):
                # tasks/cancel already made this task terminal; a run that completes on this worker
                # after the cancel must not clobber CANCELED with a non-cancel state. Terminal is final.
                return
            else:
                row.task = blob  # fresh dict reference flags the JSON column dirty

    async def get(self, task_id: str, context: ServerCallContext) -> pb.Task | None:
        owner = _task_scope(context)
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


# Shared durable task store: read/written by the SDK handler and by _DurableCancelHandler, which
# forces a terminal CANCELED into it so tasks/cancel works for parked tasks and can't be lost to an
# event-queue close.
_TASK_STORE = DurableTaskStore()


class _DurableCancelHandler(DefaultRequestHandler):
    """Make tasks/cancel terminal, including for parked tasks the SDK won't touch.

    The V2 handler only preempts a *live* producer (ActiveTask.cancel no-ops once the producer has
    finished), so cancelling a parked input-required task returns it unchanged, and cancelling a live
    run whose queue closed can leave it stuck 'working'. After delegating (which still preempts a live
    producer same-worker), force CANCELED into the returned task and the durable store so the state is
    terminal for both cases. A run on another worker still can't be preempted (LE-1699).
    """

    async def on_cancel_task(self, params, context: ServerCallContext):
        # The in-memory ActiveTaskRegistry is keyed by task id only, not flow, so without this a
        # cancel could reach a task created under a different flow's endpoint. Gate on the
        # flow-scoped store: a task this flow can't see is "not found" here (and we never reveal
        # that it exists under another flow).
        if await _TASK_STORE.get(params.id, context) is None:
            raise TaskNotFoundError
        task = await super().on_cancel_task(params, context)
        if task is not None and task.status.state != pb.TaskState.TASK_STATE_CANCELED:
            task.status.state = pb.TaskState.TASK_STATE_CANCELED
            await _TASK_STORE.save(task, context)
        return task


# One shared httpx client sends webhooks; a short timeout so a slow/hostile webhook
# can't tie up the run. Created at import (no I/O) and reused across requests; closed
# from the app lifespan via close_push_client(). The sender re-validates and DNS-pins
# each webhook at dispatch (per-dispatch client), so this shared client only carries
# the no-pin path (private webhooks allowed / allowlisted host / SSRF protection off).
_PUSH_TIMEOUT = 10.0
_PUSH_HTTP_CLIENT = httpx.AsyncClient(timeout=_PUSH_TIMEOUT)
_PUSH_CONFIG_STORE = _SafePushConfigStore(owner_resolver=_push_config_scope)
_PUSH_SENDER = _SafePushNotificationSender(_PUSH_HTTP_CLIENT, _PUSH_CONFIG_STORE)


async def close_push_client() -> None:
    """Close the shared push-notification webhook client. Wired into the app lifespan."""
    await _PUSH_HTTP_CLIENT.aclose()


# One shared handler/store/dispatcher serve every flow; the per-request flow_id
# selects the flow. The handler card carries only capabilities the SDK reads to gate
# methods: streaming=True admits message/stream + tasks/resubscribe; push_notifications=True
# admits the tasks/pushNotificationConfig methods. The real per-flow discovery card is the
# GET route. The stores do no DB work at construction, so the import-time singletons are safe.
# ponytail: streaming emits the run's lifecycle events (submitted -> working ->
# artifact -> completed) as SSE; per-token deltas would inject a stream_flow callable
# into the executor. tasks/resubscribe is best-effort same-worker live re-attach (the
# default in-memory QueueManager); a terminal or cross-worker task returns a spec error
# and tasks/get covers terminal reads. Push configs are in-memory per-worker; durable
# cross-worker re-attach and push delivery are a later slice.
_HANDLER = _DurableCancelHandler(
    agent_executor=FlowAgentExecutor(_run_flow, _resume_flow),
    task_store=_TASK_STORE,
    agent_card=pb.AgentCard(capabilities=pb.AgentCapabilities(streaming=True, push_notifications=True)),
    push_config_store=_PUSH_CONFIG_STORE,
    push_sender=_PUSH_SENDER,
)
_DISPATCHER = JsonRpcDispatcher(
    request_handler=_HANDLER,
    context_builder=_FlowContextBuilder(),
    # routes spec method names: message/send, message/stream, tasks/get, tasks/cancel,
    # tasks/resubscribe, tasks/pushNotificationConfig/{set,get,list,delete}
    enable_v0_3_compat=True,
)


# The flag guard is a route dependency so it runs BEFORE the CurrentActiveUser auth dependency
# (FastAPI resolves decorator dependencies first): a disabled route must look unmounted (404) to an
# anonymous caller, not leak a 403 from auth resolving ahead of an in-body flag check.
@router.get("/agents", dependencies=[Depends(_require_a2a_enabled)])
async def list_a2a_agents(request: Request, session: DbSession, current_user: CurrentActiveUser) -> list[dict]:
    """List the caller's own A2A-published agent flows, each with its agent-card URL.

    Authenticated and owner-scoped, mirroring the MCP-projects catalog: a public cross-user
    directory would strip the per-flow card's unguessable-id obscurity and expose other users'
    agents, so this enumerates only the calling user's agents. Each ``cardUrl`` is the public
    discovery entry point an orchestrator fetches per agent.
    """
    base = str(request.base_url).rstrip("/")
    flows = (
        await session.exec(select(Flow).where(Flow.user_id == current_user.id, Flow.flow_type == FlowType.AGENT))
    ).all()
    # a2a_enabled is bool|None; filter truthiness in Python, matching the card route's gate.
    return [
        {
            "id": str(flow.id),
            "name": flow.name,
            "description": flow.description,
            "cardUrl": f"{base}/api/v1/a2a/{flow.id}/.well-known/agent-card.json",
        }
        for flow in flows
        if flow.a2a_enabled
    ]


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
