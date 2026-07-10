import json
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.triton_server.crud import (
    create_triton_server,
    delete_triton_server,
    get_credentials,
    get_triton_server,
    list_triton_servers,
    to_read,
    update_triton_server,
)
from langflow.services.database.models.triton_server.model import (
    TritonServer,
    TritonServerCreate,
    TritonServerCredentials,
    TritonServerRead,
    TritonServerUpdate,
)

router = APIRouter(prefix="/triton_servers", tags=["TritonServers"])

_DEFAULT_TIMEOUT = 60.0
_INFER_TIMEOUT = 120.0


async def _proxy_to_triton(
    server: TritonServer,
    path: str,
    *,
    method: str = "GET",
    json_body: Any | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> httpx.Response:
    base_url = (server.base_url or "").rstrip("/")
    if not base_url:
        raise HTTPException(status_code=400, detail="Triton server base_url is empty")
    url = f"{base_url}{path}"
    headers: dict[str, str] = {}
    creds = get_credentials(server)
    if creds.auth_token:
        headers["Authorization"] = f"Bearer {creds.auth_token}"
    try:
        # trust_env=False so httpx does NOT route through the OS / registry
        # proxy. Triton is a backend service on the LAN (often localhost);
        # a system HTTP proxy (e.g. a corporate tunnel) silently breaks
        # every health/metadata/infer call with ReadTimeout -> 502.
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            if method == "GET":
                return await client.get(url, headers=headers)
            if method == "POST":
                return await client.post(url, json=json_body, headers=headers)
    except httpx.ConnectTimeout as exc:
        raise HTTPException(status_code=504, detail=f"Triton server timed out: {exc}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach Triton server: {exc}") from exc
    raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")


def _passthrough(resp: httpx.Response) -> Response:
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("Content-Type", "application/json"),
    )


@router.get("/", status_code=200)
async def list_triton_servers_route(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> list[TritonServerRead]:
    servers = await list_triton_servers(session, user_id=current_user.id)
    return [to_read(s) for s in servers]


@router.post("/", status_code=201)
async def create_triton_server_route(
    *,
    session: DbSession,
    payload: TritonServerCreate,
    current_user: CurrentActiveUser,
) -> TritonServerRead:
    try:
        server = await create_triton_server(
            session,
            user_id=current_user.id,
            name=payload.name,
            base_url=payload.base_url,
            auth_token=payload.auth_token,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return to_read(server)


@router.get("/{server_id}", status_code=200)
async def get_triton_server_route(
    *,
    session: DbSession,
    server_id: UUID,
    current_user: CurrentActiveUser,
) -> TritonServerRead:
    server = await get_triton_server(session, server_id=server_id, user_id=current_user.id)
    if server is None:
        raise HTTPException(status_code=404, detail="Triton server not found")
    return to_read(server)


@router.get("/{server_id}/credentials", status_code=200)
async def get_triton_server_credentials_route(
    *,
    session: DbSession,
    server_id: UUID,
    current_user: CurrentActiveUser,
) -> TritonServerCredentials:
    server = await get_triton_server(session, server_id=server_id, user_id=current_user.id)
    if server is None:
        raise HTTPException(status_code=404, detail="Triton server not found")
    return get_credentials(server)


@router.patch("/{server_id}", status_code=200)
async def update_triton_server_route(
    *,
    session: DbSession,
    server_id: UUID,
    payload: TritonServerUpdate,
    current_user: CurrentActiveUser,
) -> TritonServerRead:
    server = await get_triton_server(session, server_id=server_id, user_id=current_user.id)
    if server is None:
        raise HTTPException(status_code=404, detail="Triton server not found")
    try:
        updated = await update_triton_server(
            session,
            server=server,
            name=payload.name,
            base_url=payload.base_url,
            auth_token=payload.auth_token,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_read(updated)


@router.delete("/{server_id}", status_code=204)
async def delete_triton_server_route(
    *,
    session: DbSession,
    server_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    server = await get_triton_server(session, server_id=server_id, user_id=current_user.id)
    if server is None:
        raise HTTPException(status_code=404, detail="Triton server not found")
    try:
        await delete_triton_server(session, server=server)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Proxy endpoints — forward to the Triton server's HTTP API.
# The frontend never calls Triton directly; all requests go through Langflow
# so authentication, audit and (optionally) SSRF protection apply uniformly.
# ---------------------------------------------------------------------------


async def _get_owned_server(session: DbSession, server_id: UUID, user_id: UUID) -> TritonServer:
    server = await get_triton_server(session, server_id=server_id, user_id=user_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Triton server not found")
    return server


@router.get("/{server_id}/health/{kind}", status_code=200)
async def proxy_health(
    *,
    session: DbSession,
    server_id: UUID,
    kind: str,
    current_user: CurrentActiveUser,
) -> dict[str, Any]:
    if kind not in ("live", "ready"):
        raise HTTPException(status_code=400, detail="kind must be 'live' or 'ready'")
    server = await _get_owned_server(session, server_id, current_user.id)
    # Triton's /v2/health/{live,ready} returns 200 with an EMPTY body when
    # healthy — only the status code matters. Any connection / timeout
    # failure is reported as unhealthy (ok=False) so the frontend shows
    # "down" instead of raising an error banner.
    try:
        resp = await _proxy_to_triton(server, f"/v2/health/{kind}", method="GET", timeout=10.0)
    except HTTPException:
        return {"kind": kind, "ok": False, "status": 0}
    return {"kind": kind, "ok": resp.is_success, "status": resp.status_code}


@router.get("/{server_id}/metadata", status_code=200)
async def proxy_metadata(
    *,
    session: DbSession,
    server_id: UUID,
    current_user: CurrentActiveUser,
) -> Response:
    server = await _get_owned_server(session, server_id, current_user.id)
    resp = await _proxy_to_triton(server, "/v2")
    return _passthrough(resp)


@router.get("/{server_id}/models", status_code=200)
async def proxy_models(
    *,
    session: DbSession,
    server_id: UUID,
    current_user: CurrentActiveUser,
) -> dict[str, Any]:
    server = await _get_owned_server(session, server_id, current_user.id)
    resp = await _proxy_to_triton(server, "/v2/repository/index", method="POST", json_body={})
    if not resp.is_success:
        return {"models": []}
    return {"models": resp.json()}


@router.get("/{server_id}/models/{model_name}/config", status_code=200)
async def proxy_model_config(
    *,
    session: DbSession,
    server_id: UUID,
    model_name: str,
    current_user: CurrentActiveUser,
) -> Response:
    server = await _get_owned_server(session, server_id, current_user.id)
    resp = await _proxy_to_triton(server, f"/v2/models/{quote(model_name, safe='')}/config")
    return _passthrough(resp)


@router.post("/{server_id}/repository/index", status_code=200)
async def proxy_repository_index(
    *,
    session: DbSession,
    server_id: UUID,
    request: Request,
    current_user: CurrentActiveUser,
) -> dict[str, Any]:
    server = await _get_owned_server(session, server_id, current_user.id)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    resp = await _proxy_to_triton(server, "/v2/repository/index", method="POST", json_body=body)
    if not resp.is_success:
        return {"models": []}
    return {"models": resp.json()}


@router.post("/{server_id}/repository/models/{model_name}/{op}", status_code=200)
async def proxy_repository_op(
    *,
    session: DbSession,
    server_id: UUID,
    model_name: str,
    op: str,
    current_user: CurrentActiveUser,
) -> Response:
    if op not in ("load", "unload"):
        raise HTTPException(status_code=400, detail="op must be 'load' or 'unload'")
    server = await _get_owned_server(session, server_id, current_user.id)
    resp = await _proxy_to_triton(
        server,
        f"/v2/repository/models/{quote(model_name, safe='')}/{op}",
        method="POST",
        json_body={},
    )
    return _passthrough(resp)


@router.post("/{server_id}/models/{model_name}/infer", status_code=200)
async def proxy_infer(
    *,
    session: DbSession,
    server_id: UUID,
    model_name: str,
    request: Request,
    current_user: CurrentActiveUser,
) -> Response:
    server = await _get_owned_server(session, server_id, current_user.id)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    resp = await _proxy_to_triton(
        server,
        f"/v2/models/{quote(model_name, safe='')}/infer",
        method="POST",
        json_body=body,
        timeout=_INFER_TIMEOUT,
    )
    return _passthrough(resp)


@router.get("/{server_id}/metrics", status_code=200)
async def proxy_metrics(
    *,
    session: DbSession,
    server_id: UUID,
    current_user: CurrentActiveUser,
) -> Response:
    server = await _get_owned_server(session, server_id, current_user.id)
    resp = await _proxy_to_triton(server, "/v2/models/stats")
    return _passthrough(resp)
