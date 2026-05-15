"""Runtime API.

What this proves:
- The worker never receives DB credentials. It receives a short-lived run
  token. All DB-backed behavior goes through these endpoints.
- Scope claims on the token determine what is reachable. No claim, no access.
- Tenant isolation is enforced by the control plane, not by user code.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import auth
from .store import store

app = FastAPI(title="Langflow Runtime API (prototype)")


def get_claims(authorization: str = Header(...)) -> auth.RunClaims:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return auth.verify(token)
    except Exception as exc:
        raise HTTPException(401, f"invalid token: {exc}") from exc


def require_scope(claims: auth.RunClaims, scope: str) -> None:
    if not auth.has_scope(claims, scope):
        raise HTTPException(403, f"missing scope: {scope}")


# Admin helpers. Real control plane mints tokens internally; we expose this for
# the demo so a shell script can drive end-to-end flows.


class MintRequest(BaseModel):
    tenant_id: str
    user_id: str
    flow_id: str
    run_id: str
    component_id: str
    scopes: list[str]
    ttl_seconds: int = 300


class MintResponse(BaseModel):
    token: str


@app.post("/admin/mint-token", response_model=MintResponse)
def mint_token(req: MintRequest) -> MintResponse:
    token = auth.mint(
        tenant_id=req.tenant_id,
        user_id=req.user_id,
        flow_id=req.flow_id,
        run_id=req.run_id,
        component_id=req.component_id,
        scopes=req.scopes,
        ttl_seconds=req.ttl_seconds,
    )
    return MintResponse(token=token)


class SeedVariableRequest(BaseModel):
    tenant_id: str
    name: str
    value: str


@app.post("/admin/seed-variable")
def seed_variable(req: SeedVariableRequest) -> dict[str, str]:
    store.seed_variable(req.tenant_id, req.name, req.value)
    return {"status": "ok"}


@app.get("/admin/artifacts/{tenant_id}/{run_id}")
def list_artifacts(tenant_id: str, run_id: str) -> list[dict[str, Any]]:
    return store.read_artifacts(tenant_id, run_id)


@app.get("/admin/events")
def list_events() -> list[dict[str, Any]]:
    return store.read_events()


# Runtime capability endpoints. These are the only DB-backed surface the
# worker can reach.


@app.get("/runtime/variables/{name}")
def get_variable(name: str, claims: auth.RunClaims = Depends(get_claims)) -> dict[str, str]:
    require_scope(claims, f"variables:read:{name}")
    value = store.get_variable(claims.tenant_id, name)
    if value is None:
        raise HTTPException(404, f"variable not found: {name}")
    store.write_event(
        {
            "kind": "variable_read",
            "tenant_id": claims.tenant_id,
            "user_id": claims.user_id,
            "run_id": claims.run_id,
            "component_id": claims.component_id,
            "name": name,
        }
    )
    return {"name": name, "value": value}


@app.get("/runtime/memory")
def get_memory(session_id: str, claims: auth.RunClaims = Depends(get_claims)) -> list[dict[str, Any]]:
    require_scope(claims, f"memory:read:session:{session_id}")
    return store.read_memory(claims.tenant_id, session_id)


class MemoryWrite(BaseModel):
    session_id: str
    role: str
    content: str


@app.post("/runtime/memory")
def post_memory(body: MemoryWrite, claims: auth.RunClaims = Depends(get_claims)) -> dict[str, str]:
    require_scope(claims, f"memory:write:session:{body.session_id}")
    store.write_memory(
        claims.tenant_id,
        body.session_id,
        {"role": body.role, "content": body.content, "component_id": claims.component_id},
    )
    return {"status": "ok"}


class ArtifactWrite(BaseModel):
    kind: str
    data: dict[str, Any]


@app.post("/runtime/artifacts")
def post_artifact(body: ArtifactWrite, claims: auth.RunClaims = Depends(get_claims)) -> dict[str, str]:
    require_scope(claims, f"artifacts:write:run:{claims.run_id}")
    store.write_artifact(
        claims.tenant_id,
        claims.run_id,
        {"kind": body.kind, "data": body.data, "component_id": claims.component_id},
    )
    return {"status": "ok"}


class EventWrite(BaseModel):
    kind: str
    data: dict[str, Any]


@app.post("/runtime/events")
def post_event(body: EventWrite, claims: auth.RunClaims = Depends(get_claims)) -> dict[str, str]:
    require_scope(claims, f"events:write:run:{claims.run_id}")
    store.write_event(
        {
            "kind": body.kind,
            "tenant_id": claims.tenant_id,
            "run_id": claims.run_id,
            "component_id": claims.component_id,
            "data": body.data,
        }
    )
    return {"status": "ok"}
