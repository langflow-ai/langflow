"""Billing, plans, usage, and Stripe webhook endpoints.

Routes:
  GET   /api/saas/v1/plans                            — list active plans (public)
  GET   /api/saas/v1/orgs/{org_id}/billing            — get subscription details
  POST  /api/saas/v1/orgs/{org_id}/billing/checkout   — create Stripe checkout session
  GET   /api/saas/v1/orgs/{org_id}/usage              — get usage summary
  POST  /api/saas/v1/billing/webhook                  — Stripe webhook (no auth, HMAC-verified)
  GET   /api/saas/v1/audit                            — audit log (admin+)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from langflow_saas.dependencies import CurrentOrgContext, RequireAdmin, assert_org_match
from langflow_saas.models import (
    AuditLog,
    Organization,
    Plan,
    PlanRead,
    Subscription,
    SubscriptionRead,
    UsageMetric,
    UsageRecord,
    UsageSummary,
)
from langflow_saas.services import get_billing_service
from langflow_saas.settings import get_saas_settings

router = APIRouter(tags=["Billing & Plans"])


# ---------------------------------------------------------------------------
# Plans (public, no auth)
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=list[PlanRead])
async def list_plans():
    """Return all active plans.  Safe to call without authentication."""
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(select(Plan).where(Plan.is_active == True))  # noqa: E712
        return [PlanRead.model_validate(p) for p in result.all()]


# ---------------------------------------------------------------------------
# Subscription info
# ---------------------------------------------------------------------------


@router.get("/orgs/{org_id}/billing", response_model=SubscriptionRead | None)
async def get_subscription(org_id: UUID, ctx: CurrentOrgContext):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        sub_result = await db.exec(select(Subscription).where(Subscription.org_id == org_id))
        sub = sub_result.first()
        if not sub:
            return None

        plan_result = await db.exec(select(Plan).where(Plan.id == sub.plan_id))
        plan = plan_result.first()
        if not plan:
            return None

        return SubscriptionRead(
            id=sub.id,
            org_id=sub.org_id,
            status=sub.status,
            plan=PlanRead.model_validate(plan),
            current_period_end=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            trial_end=sub.trial_end,
        )


class CheckoutRequest(PlanRead):
    stripe_price_id: str
    billing_cycle: str = "monthly"  # "monthly" | "yearly"


@router.post("/orgs/{org_id}/billing/checkout")
async def create_checkout(org_id: UUID, request: Request, ctx: RequireAdmin):
    """Create a Stripe Checkout Session and return the redirect URL."""
    assert_org_match(org_id, ctx)
    settings = get_saas_settings()
    if not settings.billing_enabled:
        raise HTTPException(501, "Billing is not enabled on this instance.")

    body = await request.json()
    price_id: str = body.get("stripe_price_id", "")
    if not price_id:
        raise HTTPException(400, "stripe_price_id is required.")

    from langflow.services.deps import session_scope

    async with session_scope() as db:
        org_result = await db.exec(select(Organization).where(Organization.id == org_id))
        org = org_result.first()
        if not org:
            raise HTTPException(404, "Organization not found.")

        # Fetch owner email from Langflow user table.
        from langflow.services.database.models.user.model import User

        user_result = await db.exec(select(User).where(User.id == org.owner_id))
        owner = user_result.first()
        owner_email = getattr(owner, "email", "") or f"{org.slug}@noemail.local"

    url = await get_billing_service().create_checkout_session(
        org_id=org_id,
        org_name=org.name,
        owner_email=owner_email,
        stripe_price_id=price_id,
        success_url=f"{settings.app_base_url}/settings/billing?success=1",
        cancel_url=f"{settings.app_base_url}/settings/billing?canceled=1",
    )
    return {"checkout_url": url}


# ---------------------------------------------------------------------------
# Usage summary
# ---------------------------------------------------------------------------


@router.get("/orgs/{org_id}/usage", response_model=UsageSummary)
async def get_usage(org_id: UUID, ctx: CurrentOrgContext):
    assert_org_match(org_id, ctx)
    settings = get_saas_settings()
    from langflow.services.deps import session_scope
    from sqlalchemy import func

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with session_scope() as db:
        # Get plan limits.
        org_result = await db.exec(select(Organization).where(Organization.id == org_id))
        org = org_result.first()
        plan: Plan | None = None
        if org and org.plan_id:
            plan_result = await db.exec(select(Plan).where(Plan.id == org.plan_id))
            plan = plan_result.first()

        max_flows = plan.max_flows if plan else settings.default_max_flows
        max_exec = plan.max_executions_per_day if plan else settings.default_max_executions_per_day
        max_storage = plan.max_storage_mb if plan else settings.default_max_storage_mb

        # Count executions today.
        exec_result = await db.exec(
            select(func.sum(UsageRecord.value)).where(
                UsageRecord.org_id == org_id,
                UsageRecord.metric == UsageMetric.FLOW_EXECUTION,
                UsageRecord.recorded_at >= today_start,
            )
        )
        execs_today = int(exec_result.first() or 0)

        # Count API calls today.
        api_result = await db.exec(
            select(func.sum(UsageRecord.value)).where(
                UsageRecord.org_id == org_id,
                UsageRecord.metric == UsageMetric.API_CALL,
                UsageRecord.recorded_at >= today_start,
            )
        )
        api_calls_today = int(api_result.first() or 0)

        # Storage (sum of all storage_bytes records for this org).
        storage_result = await db.exec(
            select(func.sum(UsageRecord.value)).where(
                UsageRecord.org_id == org_id, UsageRecord.metric == UsageMetric.STORAGE_BYTES
            )
        )
        storage_bytes = int(storage_result.first() or 0)

        # Count flows from Langflow's flows table for org members.
        # We aggregate flows belonging to all members of the org.
        from langflow.services.database.models.flow.model import Flow

        from langflow_saas.models import UserOrganization

        member_result = await db.exec(select(UserOrganization.user_id).where(UserOrganization.org_id == org_id))
        member_ids = [r for r in member_result.all()]
        flow_count = 0
        if member_ids:
            flow_count_result = await db.exec(
                select(func.count(Flow.id)).where(Flow.user_id.in_(member_ids))  # type: ignore[attr-defined]
            )
            flow_count = int(flow_count_result.first() or 0)

    return UsageSummary(
        org_id=org_id,
        executions_today=execs_today,
        executions_limit=max_exec,
        flows_count=flow_count,
        flows_limit=max_flows,
        storage_mb=round(storage_bytes / (1024 * 1024), 2),
        storage_limit_mb=max_storage,
        api_calls_today=api_calls_today,
        plan_slug=plan.slug if plan else "free",
    )


# ---------------------------------------------------------------------------
# Stripe Webhook (no auth — Stripe HMAC-verified)
# ---------------------------------------------------------------------------


@router.post("/billing/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request):
    settings = get_saas_settings()
    if not settings.billing_enabled:
        raise HTTPException(501, "Billing not enabled.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        result = await get_billing_service().handle_webhook(payload=payload, sig_header=sig_header)
    except Exception as exc:
        raise HTTPException(400, f"Webhook processing failed: {exc}") from exc

    return result


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


@router.get("/audit")
async def get_audit_log(
    ctx: RequireAdmin,
    limit: int = 100,
    offset: int = 0,
):
    """Paginated audit log for the current organization."""
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(
            select(AuditLog)
            .where(AuditLog.org_id == ctx.org_id)
            .order_by(AuditLog.created_at.desc())  # type: ignore[union-attr]
            .offset(offset)
            .limit(min(limit, 500))
        )
        entries = result.all()

    return [
        {
            "id": str(e.id),
            "action": e.action,
            "user_id": str(e.user_id) if e.user_id else None,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "metadata": e.log_metadata,
            "ip_address": e.ip_address,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]
