"""Org-scoped flow management endpoints.

Routes:
  GET    /api/saas/v1/orgs/{org_id}/flows             — list all flows owned by the org
  POST   /api/saas/v1/orgs/{org_id}/flows/{flow_id}/assign   — assign an existing flow to the org
  DELETE /api/saas/v1/orgs/{org_id}/flows/{flow_id}/assign   — unassign (remove org ownership)

These endpoints operate on Langflow's native ``flow`` rows via a shadow table
(``saas_flow_org``) — Langflow's own schema is never modified.

Newly created flows are auto-assigned by FlowOwnershipMiddleware so in most
cases callers never need the assign/unassign endpoints directly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import SQLModel, select

from langflow_saas.dependencies import CurrentOrgContext, RequireAdmin, assert_org_match
from langflow_saas.models import FlowOrg

router = APIRouter(tags=["Org Flows"])


# ---------------------------------------------------------------------------
# Response schema (mirrors Langflow's FlowBase fields we care about)
# ---------------------------------------------------------------------------


class OrgFlowRead(SQLModel):
    id: UUID
    name: str
    description: str | None = None
    user_id: UUID | None = None
    updated_at: datetime | None = None
    assigned_at: datetime


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/orgs/{org_id}/flows", response_model=list[OrgFlowRead])
async def list_org_flows(org_id: UUID, ctx: CurrentOrgContext):
    """Return all flows assigned to this org, enriched with Langflow metadata."""
    assert_org_match(org_id, ctx)

    from langflow.services.database.models.flow.model import Flow
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        # Get all flow_org mappings for this org.
        fo_result = await db.exec(select(FlowOrg).where(FlowOrg.org_id == org_id))
        flow_orgs = fo_result.all()

        if not flow_orgs:
            return []

        flow_id_to_assigned = {fo.flow_id: fo.assigned_at for fo in flow_orgs}
        flow_ids = list(flow_id_to_assigned.keys())

        # Fetch the actual Langflow flow rows.
        flows_result = await db.exec(select(Flow).where(Flow.id.in_(flow_ids)))  # type: ignore[attr-defined]
        flows = flows_result.all()

    return [
        OrgFlowRead(
            id=UUID(str(f.id)),
            name=f.name,
            description=getattr(f, "description", None),
            user_id=UUID(str(f.user_id)) if f.user_id else None,
            updated_at=getattr(f, "updated_at", None),
            assigned_at=flow_id_to_assigned[UUID(str(f.id))],
        )
        for f in flows
    ]


@router.post(
    "/orgs/{org_id}/flows/{flow_id}/assign",
    status_code=status.HTTP_201_CREATED,
)
async def assign_flow(org_id: UUID, flow_id: UUID, ctx: RequireAdmin):
    """Manually assign an existing flow to this org.

    Useful for flows created before the plugin was installed, or flows created
    by users who weren't in an org at the time.
    """
    assert_org_match(org_id, ctx)

    from langflow.services.database.models.flow.model import Flow
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        # Verify the flow exists in Langflow.
        flow_result = await db.exec(select(Flow).where(Flow.id == flow_id))  # type: ignore[arg-type]
        if not flow_result.first():
            raise HTTPException(404, "Flow not found.")

        # Reject if already assigned to a *different* org.
        existing = await db.exec(select(FlowOrg).where(FlowOrg.flow_id == flow_id))
        existing_fo = existing.first()
        if existing_fo:
            if existing_fo.org_id == org_id:
                return {"ok": True, "already_assigned": True}
            raise HTTPException(
                409,
                f"Flow is already assigned to org {existing_fo.org_id}. Unassign it first.",
            )

        db.add(FlowOrg(flow_id=flow_id, org_id=org_id, assigned_by=ctx.user_id))
        await db.commit()

    return {"ok": True, "org_id": str(org_id), "flow_id": str(flow_id)}


@router.delete(
    "/orgs/{org_id}/flows/{flow_id}/assign",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unassign_flow(org_id: UUID, flow_id: UUID, ctx: RequireAdmin):
    """Remove org ownership of a flow (the flow itself is NOT deleted)."""
    assert_org_match(org_id, ctx)

    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(select(FlowOrg).where(FlowOrg.flow_id == flow_id, FlowOrg.org_id == org_id))
        fo = result.first()
        if not fo:
            raise HTTPException(404, "Flow is not assigned to this org.")

        await db.delete(fo)
        await db.commit()
