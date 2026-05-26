"""Run-token mint/verify and scope matching.

Prototype simplification: HS256 with a shared secret. Production design calls
for asymmetric signing plus mutual TLS between worker and Runtime API.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import jwt

ALGO = "HS256"
SECRET = os.environ.get("RUNTIME_API_SECRET", "dev-secret-change-me")


@dataclass(frozen=True)
class RunClaims:
    tenant_id: str
    user_id: str
    flow_id: str
    run_id: str
    component_id: str
    scopes: tuple[str, ...]
    exp: int


def mint(
    *,
    tenant_id: str,
    user_id: str,
    flow_id: str,
    run_id: str,
    component_id: str,
    scopes: list[str],
    ttl_seconds: int = 300,
) -> str:
    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "flow_id": flow_id,
        "run_id": run_id,
        "component_id": component_id,
        "scopes": scopes,
        "exp": int(time.time()) + ttl_seconds,
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def verify(token: str) -> RunClaims:
    payload = jwt.decode(token, SECRET, algorithms=[ALGO])
    return RunClaims(
        tenant_id=payload["tenant_id"],
        user_id=payload["user_id"],
        flow_id=payload["flow_id"],
        run_id=payload["run_id"],
        component_id=payload["component_id"],
        scopes=tuple(payload["scopes"]),
        exp=payload["exp"],
    )


def has_scope(claims: RunClaims, required: str) -> bool:
    """Exact-match scope check.

    Scopes look like 'variables:read:openai_api_key' or
    'memory:write:session:abc'. Prototype keeps matching literal; a real
    implementation would support hierarchical or category scopes.
    """
    return required in claims.scopes
