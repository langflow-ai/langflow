"""Multiplayer flow endpoints (v2): operation batches, revisions after a revision, and joins.

- ``POST /api/v2/flows/{id}/ops`` body ``{request_id, base_revision?, operations}``:
  200 ``{status: applied|already_applied, revision, start_revision, end_revision}``;
  422 refused batch (``code``, ``violations``, ``latest_revision``);
  409 ``REQUEST_ID_REUSED`` or ``BASE_REVISION_AHEAD`` (with ``latest_revision``).
- ``GET /api/v2/flows/{id}/revisions?after=R``:
  ``{latest_revision, retention_gap, revisions: [{revision, operations}]}``.
- ``GET /api/v2/flows/{id}``: ``{revision, data}``.

They need PostgreSQL and the flow history (``flow_history_enabled``); otherwise 501.
Permissions are those of the v1 flow read and write paths.
"""

from __future__ import annotations

import re
import time
from typing import Annotated, Any
from uuid import UUID

import orjson
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from lfx.log.logger import logger
from sqlalchemy.orm import defer
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import cross_user_fetch_enabled, deny_to_404
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from langflow.services.flow_multiplayer import bench, config, reads
from langflow.services.flow_multiplayer.writes import OpsRefusedError, OpsRequest, apply_ops

router = APIRouter(prefix="/flows", tags=["Flows (multiplayer)"])
bench_router = APIRouter(prefix="/bench/flow-ops", tags=["Bench"], include_in_schema=False)

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$")
_JSON = "application/json"
_WRITE_DENIED = "You don't have permission to edit this flow."
_WRITE_FAILED = (
    b'{"detail":{"code":"WRITE_FAILED","message":"The write did not commit. Retry with the same request_id."}}'
)


def multiplayer_available(session: Any) -> bool:
    from langflow.services.flow_history.recorder import flow_history_enabled

    return session.get_bind().dialect.name == "postgresql" and flow_history_enabled()


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "code": "MULTIPLAYER_UNAVAILABLE",
            "message": "Multiplayer flow writes need PostgreSQL and the flow history (LANGFLOW_FLOW_HISTORY_ENABLED).",
        },
    )


async def load_flow_header(session: Any, flow_id: UUID, user: Any, act: FlowAction) -> Flow:
    """The flow row without ``data``, after the permission check of the v1 flow routes (404/403)."""
    statement = select(Flow).options(defer(Flow.data, raiseload=True)).where(Flow.id == flow_id)
    if not await cross_user_fetch_enabled():
        statement = statement.where(Flow.user_id == user.id)
    flow = (await session.exec(statement)).first()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        await ensure_flow_permission(
            user,
            act,
            flow_id=flow_id,
            flow_user_id=flow.user_id,
            workspace_id=flow.workspace_id,
            folder_id=flow.folder_id,
        )
    except HTTPException as exc:
        if act == FlowAction.WRITE and exc.status_code == status.HTTP_403_FORBIDDEN:
            try:
                await ensure_flow_permission(
                    user,
                    FlowAction.READ,
                    flow_id=flow_id,
                    flow_user_id=flow.user_id,
                    workspace_id=flow.workspace_id,
                    folder_id=flow.folder_id,
                )
            except HTTPException as read_exc:
                raise deny_to_404(read_exc, detail="Flow not found") from read_exc
            raise HTTPException(status_code=403, detail=_WRITE_DENIED) from exc
        raise deny_to_404(exc, detail="Flow not found") from exc
    return flow


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": message})


def parse_ops_body(raw: bytes) -> OpsRequest:
    try:
        body = orjson.loads(raw)
    except orjson.JSONDecodeError as exc:
        msg = "The body is not JSON."
        raise _bad_request(msg) from exc
    if not isinstance(body, dict):
        msg = "The body must be an object."
        raise _bad_request(msg)
    request_id = body.get("request_id")
    if not isinstance(request_id, str) or not _UUID_RE.match(request_id):
        msg = "request_id must be a UUID."
        raise _bad_request(msg)
    operations = body.get("operations")
    if not isinstance(operations, list):
        msg = "operations must be a list."
        raise _bad_request(msg)
    base_revision = body.get("base_revision")
    if base_revision is not None and (not isinstance(base_revision, int) or base_revision < 0):
        msg = "base_revision must be a revision number."
        raise _bad_request(msg)
    return OpsRequest(
        request_id=str(UUID(request_id)),
        base_revision=base_revision,
        operations_json=orjson.dumps(operations),
        count=len(operations),
    )


@router.post("/{flow_id}/ops")
async def post_flow_ops(flow_id: UUID, request: Request, current_user: CurrentActiveUser) -> Response:
    """Apply one operation batch to the flow's latest revision."""
    bench.mark_handler()
    with bench.timed("parse"):
        raw = await request.body()
        ops_request = parse_ops_body(raw)

    async def authorize(session: Any) -> None:
        """The write path's permission check, in the write's own transaction (before its lock)."""
        with bench.timed("auth"):
            if not multiplayer_available(session):
                raise _unavailable()
            flow = await load_flow_header(session, flow_id, current_user, FlowAction.WRITE)
            if flow.locked:
                raise HTTPException(status_code=423, detail="Flow is locked. Unlock it before making changes.")
            if flow.user_id is None:
                raise HTTPException(status_code=403, detail=_WRITE_DENIED)

    try:
        answer = await apply_ops(flow_id, current_user.id, ops_request, authorize=authorize)
    except OpsRefusedError as refusal:
        return Response(orjson.dumps({"detail": refusal.detail}), status_code=refusal.status, media_type=_JSON)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 -- answered as a 500 the client retries with the same request_id
        await logger.awarning("Flow ops write failed", flow_id=str(flow_id), error_type=type(exc).__name__)
        return Response(_WRITE_FAILED, status_code=500, media_type=_JSON)
    with bench.timed("respond"):
        return Response(orjson.dumps(answer), media_type=_JSON)


@router.get("/{flow_id}/revisions")
async def get_flow_revisions(
    flow_id: UUID, current_user: CurrentActiveUser, after: Annotated[int, Query(ge=0)] = 0
) -> Response:
    """The revisions after ``after``, or ``retention_gap`` when they are no longer in the log."""
    bench.mark_handler()
    async with session_scope() as session:
        if not multiplayer_available(session):
            raise _unavailable()
        with bench.timed("auth"):
            flow = await load_flow_header(session, flow_id, current_user, FlowAction.READ)
        with bench.timed("body"):
            body = await reads.revisions_body(session, flow_id, after, flow.latest_revision)
        closing = time.perf_counter()
    bench.add("close", (time.perf_counter() - closing) * 1000)
    with bench.timed("respond"):
        return Response(body, media_type=_JSON)


@router.get("/{flow_id}")
async def join_flow(flow_id: UUID, current_user: CurrentActiveUser) -> Response:
    """The flow's graph at a revision; the client then reads the revisions after it."""
    bench.mark_handler()
    graph = None
    try:
        async with session_scope() as session:
            if not multiplayer_available(session):
                raise _unavailable()
            with bench.timed("auth"):
                flow = await load_flow_header(session, flow_id, current_user, FlowAction.READ)
            graph = await reads.join_graph(session, flow_id)
            closing = time.perf_counter()
        bench.add("close", (time.perf_counter() - closing) * 1000)
        if graph is None:
            raise HTTPException(status_code=404, detail="Flow not found")
        with bench.timed("respond"):
            if flow.user_id != current_user.id:
                graph.text = _strip_secrets(graph.text)
            return graph.response(reads.join_body(graph))
    except BaseException:
        if graph is not None:
            graph.close()
        raise


def _strip_secrets(text: str) -> str:
    from langflow.utils.flow_secrets import strip_secret_field_values

    return orjson.dumps(strip_secret_field_values(orjson.loads(text))).decode()


async def v1_current_flow_response(session: Any, flow_id: UUID, current_user: Any) -> Response:
    """The v1 flow read with the current graph, spliced in as JSON text (no parse, no re-encode)."""
    from langflow.services.database.models.flow.model import FlowRead
    from langflow.services.flow_multiplayer.oplog import wal_version_token

    bench.mark_handler()
    with bench.timed("auth"):
        flow = await load_flow_header(session, flow_id, current_user, FlowAction.READ)
    graph = await reads.current_graph(session, flow_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        with bench.timed("respond"):
            fields = {name: getattr(flow, name, None) for name in FlowRead.model_fields if name != "data"}
            fields["data"] = None
            fields["latest_revision"] = max(graph.revision, flow.latest_revision)
            fields["current_revision"] = graph.revision
            if config.write_mode() == "wal":
                fields["version_token"] = wal_version_token(flow.version_token, flow.id, graph.revision)
            header = FlowRead.model_validate(fields).model_dump_json().encode()
            text = graph.text if flow.user_id == current_user.id else _strip_secrets(graph.text)
            marker = b'"data":null'
            position = header.find(marker)
            body = header[:position] + b'"data":' + text.encode() + header[position + len(marker) :]
            return graph.response(body)
    except BaseException:
        graph.close()
        raise


def _bench_only() -> None:
    if not config.bench_enabled():
        raise HTTPException(status_code=404, detail="Not Found")


@bench_router.get("/export")
async def bench_export() -> Response:
    """Every measurement record since the last reset, as JSON lines (LANGFLOW_OPS_BENCH=1 only)."""
    _bench_only()
    return Response(bench.export_jsonl(), media_type="application/x-ndjson")


@bench_router.post("/reset")
async def bench_reset() -> Response:
    _bench_only()
    bench.reset()
    return Response(b'{"reset":true}', media_type=_JSON)
