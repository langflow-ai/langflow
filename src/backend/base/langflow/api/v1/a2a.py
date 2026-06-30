"""A2A protocol routes.

F2 ships the public per-flow discovery endpoint that serves a spec-valid agent
card. The whole surface is gated behind ``LANGFLOW_A2A_ENABLED`` (default off):
the router is mounted unconditionally and a per-request guard returns 404 when
the flag is off, so the route is indistinguishable from "not mounted". This
mirrors the extensions router and avoids the import-time / env-file ordering
trap of reading a module-level flag.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from lfx.services.deps import get_settings_service
from sqlmodel import select

from langflow.api.utils import DbSession
from langflow.api.v1.a2a_utils import build_agent_card
from langflow.services.database.models import Flow
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


@router.get("/{flow_id}/.well-known/agent-card.json")
async def get_agent_card(flow_id: UUID, request: Request, session: DbSession) -> dict:
    """Serve the spec-valid A2A agent card for an agent-typed, a2a_enabled flow.

    Public by design: the A2A public agent card is unauthenticated by spec, so
    gating it behind login would break standard discovery (F6 owns the
    authenticated extended card). Returns 404 when the flag is off, the flow
    does not exist, the flow is not flow_type=agent, or a2a_enabled is falsy.
    """
    _require_a2a_enabled()

    flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
    if flow is None or flow.flow_type != FlowType.AGENT or not flow.a2a_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    # F3 owns the final JSON-RPC path; F2 ships a stable per-flow URL.
    rpc_url = str(request.base_url).rstrip("/") + f"/api/v1/a2a/{flow_id}/jsonrpc"
    return await build_agent_card(flow, rpc_url=rpc_url, session=session)
