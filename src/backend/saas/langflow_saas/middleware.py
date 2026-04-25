"""ASGI middleware for the SaaS plugin.

Three middleware classes, applied outermost-first via plugin.py:

  RateLimitMiddleware        — Redis sliding-window rate limiting per user/IP.
  TenantContextMiddleware    — Resolves org membership from JWT + X-Org-ID header,
                               stores OrgContextData in request.state.saas_context.
  QuotaEnforcementMiddleware — Enforces per-org daily execution quotas on run endpoints.

Upgrade safety: these classes import from Langflow only via clearly bounded
helpers (token decoding, DB session).  If those helpers move in a future
Langflow version, update _extract_user_id() and _open_db() here — nothing else.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from langflow_saas.models import OrgRole, UsageMetric
from langflow_saas.settings import get_saas_settings

if TYPE_CHECKING:
    from langflow_saas.models import Organization, Plan

logger = logging.getLogger("langflow_saas.middleware")


# ---------------------------------------------------------------------------
# Shared context object stored on request.state
# ---------------------------------------------------------------------------


@dataclass
class OrgContextData:
    """Resolved tenant context stored on every authenticated API request."""

    user_id: UUID
    username: str
    org_id: UUID
    org_slug: str
    role: OrgRole
    plan_slug: str
    rpm_limit: int


# ---------------------------------------------------------------------------
# Helpers: integrate with Langflow internals in ONE place
# ---------------------------------------------------------------------------


def _extract_token(request: Request) -> str | None:
    """Pull JWT / API key from request using the same precedence as Langflow."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    token = request.cookies.get("access_token_lf")
    if token:
        return token
    return request.headers.get("x-api-key") or request.query_params.get("x-api-key")


async def _resolve_user_id_from_token(token: str) -> UUID | None:
    """Decode JWT and return user_id without hitting the DB.

    Langflow integration point: imports get_settings_service and PyJWT directly.
    If Langflow changes its JWT structure, update only this function.
    """
    try:
        import jwt as pyjwt
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()
        algo = settings_service.auth_settings.ALGORITHM.value
        if settings_service.auth_settings.ALGORITHM.is_asymmetric():
            key = settings_service.auth_settings.PUBLIC_KEY
        else:
            key = settings_service.auth_settings.SECRET_KEY.get_secret_value()

        payload = pyjwt.decode(token, key, algorithms=[algo], options={"verify_exp": True})
        sub = payload.get("sub")
        if not sub:
            return None
        return UUID(sub)
    except Exception:  # noqa: BLE001
        return None


async def _resolve_user_id_from_api_key(api_key: str) -> tuple[UUID, str] | None:
    """Look up (user_id, username) from an API key via Langflow's DB.

    Opens its own short-lived DB session so it's safe to call from middleware.
    """
    try:
        from langflow.services.database.models.api_key.model import ApiKey
        from langflow.services.database.models.user.model import User
        from langflow.services.deps import session_scope
        from sqlmodel import select

        async with session_scope() as db:
            result = await db.exec(
                select(ApiKey, User)
                .join(User, User.id == ApiKey.user_id)  # type: ignore[arg-type]
                .where(ApiKey.api_key == api_key, ApiKey.is_active == True)  # noqa: E712
            )
            row = result.first()
            if row:
                api_key_obj, user = row
                return UUID(str(user.id)), user.username
    except Exception:  # noqa: BLE001
        pass
    return None


async def _get_username(user_id: UUID) -> str:
    """Fetch username for a user_id from Langflow's user table."""
    try:
        from langflow.services.database.models.user.model import User
        from langflow.services.deps import session_scope
        from sqlmodel import select

        async with session_scope() as db:
            result = await db.exec(select(User).where(User.id == user_id))  # type: ignore[arg-type]
            user = result.first()
            return user.username if user else str(user_id)
    except Exception:  # noqa: BLE001
        return str(user_id)


async def _bootstrap_personal_org(db, user_id: UUID, username: str):
    """Create a personal org + OWNER membership for a first-time user.

    Called lazily from TenantContextMiddleware when a valid user has no memberships.
    Returns the newly created UserOrganization, or None on failure.
    """
    import re
    from datetime import datetime, timezone

    from sqlmodel import select

    from langflow_saas.models import Organization, OrgRole, Plan, UserOrganization

    try:
        # Pick up the Free plan if available; leave plan_id=None otherwise.
        plan_result = await db.exec(select(Plan).where(Plan.slug == "free", Plan.is_active == True))  # noqa: E712
        free_plan = plan_result.first()

        # Build a slug guaranteed to be unique: personal-{hex uuid}.
        base_slug = re.sub(r"[^a-z0-9]+", "-", username.lower()).strip("-")[:50]
        slug_candidate = base_slug
        attempt = 0
        while True:
            collision = await db.exec(select(Organization).where(Organization.slug == slug_candidate))
            if not collision.first():
                break
            attempt += 1
            slug_candidate = f"{base_slug}-{attempt}"

        now = datetime.now(timezone.utc)
        org = Organization(
            name=f"{username}'s workspace",
            slug=slug_candidate,
            owner_id=user_id,
            plan_id=free_plan.id if free_plan else None,
            is_personal=True,
            created_at=now,
            updated_at=now,
        )
        db.add(org)
        await db.flush()  # populate org.id before referencing it

        membership = UserOrganization(
            user_id=user_id,
            org_id=org.id,
            role=OrgRole.OWNER,
            created_at=now,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(membership)

        logger.info("langflow-saas: created personal org %s for user %s", org.slug, username)
        return membership
    except Exception:
        logger.exception("langflow-saas: failed to bootstrap personal org for user %s", username)
        await db.rollback()
        return None


# ---------------------------------------------------------------------------
# Redis helpers (graceful no-op when Redis is unavailable)
# ---------------------------------------------------------------------------


def _get_redis():
    """Return a Redis client or None if Redis is not reachable."""
    try:
        import redis.asyncio as aioredis

        settings = get_saas_settings()
        return aioredis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# 1. Rate Limit Middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter backed by Redis.

    Key structure: ``saas:rl:{user_id_or_ip}:{unix_minute}``

    Degrades gracefully (allows requests) when Redis is unavailable so that
    a Redis outage never takes down the API.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_saas_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        if not any(request.url.path.startswith(p) for p in settings.rate_limit_paths):
            return await call_next(request)

        # Determine a stable identity key (user_id preferred, IP fallback).
        key_id: str | None = None
        rpm_limit = settings.rate_limit_default_rpm

        # Cheaply check for existing resolved context (set by TenantContextMiddleware
        # when it runs *before* this one — ordering is set in plugin.py).
        ctx: OrgContextData | None = getattr(request.state, "saas_context", None)
        if ctx:
            key_id = str(ctx.user_id)
            rpm_limit = ctx.rpm_limit
        else:
            token = _extract_token(request)
            if token:
                uid = await _resolve_user_id_from_token(token)
                if uid:
                    key_id = str(uid)

        if not key_id:
            forwarded_for = request.headers.get("X-Forwarded-For")
            key_id = forwarded_for or request.client.host if request.client else "unknown"

        redis = _get_redis()
        if redis is None:
            return await call_next(request)

        try:
            minute_bucket = int(time.time()) // 60
            redis_key = f"saas:rl:{key_id}:{minute_bucket}"
            burst_limit = rpm_limit * settings.rate_limit_burst_multiplier

            async with redis:
                current = await redis.incr(redis_key)
                if current == 1:
                    await redis.expire(redis_key, 120)  # TTL: 2 minutes

            reset_ts = (minute_bucket + 1) * 60
            remaining = max(0, burst_limit - current)

            if current > burst_limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please slow down."},
                    headers={
                        "X-RateLimit-Limit": str(burst_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_ts),
                        "Retry-After": "60",
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(burst_limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_ts)
            return response
        except Exception:  # noqa: BLE001
            # Redis errors must never block the request.
            return await call_next(request)


# ---------------------------------------------------------------------------
# 2. Tenant Context Middleware
# ---------------------------------------------------------------------------


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Resolve the authenticated user's active organization and store it in
    ``request.state.saas_context`` as an ``OrgContextData`` instance.

    Logic:
    1. Skip non-API paths (static assets, health checks).
    2. Extract JWT or API key from the request.
    3. Decode user_id from JWT (no DB hit) or look up API key (one DB query).
    4. Determine active org:  use ``X-Org-ID`` header if present, else the
       user's single org (auto-resolve), else skip if user has multiple orgs
       and ``require_org_header`` is True.
    5. Load the org's plan details and store the resolved context.

    On any failure the middleware allows the request through so Langflow's
    own auth layer returns the proper 401/403.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only process API paths.
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        try:
            await self._set_context(request)
        except Exception:  # noqa: BLE001
            pass  # Let Langflow's auth handle it.

        return await call_next(request)

    async def _set_context(self, request: Request) -> None:
        settings = get_saas_settings()

        token = _extract_token(request)
        if not token:
            return

        # Resolve user identity.
        user_id: UUID | None = None
        username: str = ""

        # Try JWT first (no DB hit).
        user_id = await _resolve_user_id_from_token(token)
        if user_id:
            username = await _get_username(user_id)
        else:
            # Might be an API key.
            result = await _resolve_user_id_from_api_key(token)
            if result:
                user_id, username = result

        if not user_id:
            return

        from langflow.services.deps import session_scope
        from sqlmodel import select

        from langflow_saas.models import Organization, Plan, UserOrganization

        async with session_scope() as db:
            # Find the org context.
            org_id_header = request.headers.get("X-Org-ID")
            membership: UserOrganization | None = None

            if org_id_header:
                try:
                    requested_org_id = UUID(org_id_header)
                except ValueError:
                    return
                result = await db.exec(
                    select(UserOrganization).where(
                        UserOrganization.user_id == user_id,
                        UserOrganization.org_id == requested_org_id,
                    )
                )
                membership = result.first()
            else:
                # Auto-resolve: get all memberships, pick the personal org or the
                # only org if the user belongs to exactly one.
                result = await db.exec(select(UserOrganization).where(UserOrganization.user_id == user_id))
                memberships = result.all()
                if not memberships:
                    if settings.auto_create_personal_org:
                        bootstrapped = await _bootstrap_personal_org(db, user_id, username)
                        if bootstrapped:
                            memberships = [bootstrapped]
                        else:
                            return
                    else:
                        return
                if len(memberships) == 1:
                    membership = memberships[0]
                else:
                    # Multiple orgs: require explicit header if configured.
                    if settings.require_org_header:
                        return
                    # Otherwise pick personal org as default.
                    personal_orgs = []
                    for m in memberships:
                        org_result = await db.exec(
                            select(Organization).where(Organization.id == m.org_id, Organization.is_personal == True)  # noqa: E712
                        )
                        if org_result.first():
                            personal_orgs.append(m)
                    membership = personal_orgs[0] if personal_orgs else memberships[0]

            if not membership:
                return

            # Load org + plan.
            org_result = await db.exec(
                select(Organization).where(Organization.id == membership.org_id, Organization.is_active == True)  # noqa: E712
            )
            org: Organization | None = org_result.first()
            if not org:
                return

            plan_slug = "free"
            rpm_limit = settings.default_max_executions_per_day // (60 * 24)  # crude default
            rpm_limit = max(rpm_limit, settings.rate_limit_default_rpm)

            if org.plan_id:
                plan_result = await db.exec(select(Plan).where(Plan.id == org.plan_id))
                plan: Plan | None = plan_result.first()
                if plan:
                    plan_slug = plan.slug
                    rpm_limit = plan.rpm_limit

            request.state.saas_context = OrgContextData(
                user_id=user_id,
                username=username,
                org_id=membership.org_id,
                org_slug=org.slug,
                role=membership.role,
                plan_slug=plan_slug,
                rpm_limit=rpm_limit,
            )


# ---------------------------------------------------------------------------
# 3. Quota Enforcement Middleware
# ---------------------------------------------------------------------------

# Paths that count as a "flow execution" for metering.
_EXECUTION_PATHS = ("/api/v1/run/", "/api/v2/flows/")


class QuotaEnforcementMiddleware(BaseHTTPMiddleware):
    """Block flow executions when the org has exhausted its daily quota.

    Only queries the DB for POST requests on execution paths.  All other
    requests pass through with no overhead.

    After a successful execution (2xx response), a UsageRecord is inserted
    asynchronously so the quota counter is updated for the next request.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_saas_settings()

        if not settings.billing_enabled:
            return await call_next(request)

        is_execution = request.method == "POST" and any(request.url.path.startswith(p) for p in _EXECUTION_PATHS)
        if not is_execution:
            return await call_next(request)

        ctx: OrgContextData | None = getattr(request.state, "saas_context", None)
        if not ctx:
            return await call_next(request)

        # Check quota before executing.
        quota_ok, limit, used = await self._check_execution_quota(ctx.org_id)
        if not quota_ok:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Daily execution quota exceeded ({used}/{limit}). "
                    "Upgrade your plan or wait until midnight UTC."
                },
                headers={"X-Quota-Limit": str(limit), "X-Quota-Used": str(used)},
            )

        response = await call_next(request)

        # Record usage after a successful execution.
        if 200 <= response.status_code < 300:
            await self._record_execution(ctx)

        return response

    async def _check_execution_quota(self, org_id: UUID) -> tuple[bool, int, int]:
        """Return (quota_ok, limit, used_today)."""
        try:
            from langflow.services.deps import session_scope
            from sqlalchemy import func
            from sqlmodel import select

            from langflow_saas.models import Organization, Plan, UsageRecord

            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

            async with session_scope() as db:
                # Get limit from plan.
                org_result = await db.exec(select(Organization).where(Organization.id == org_id))
                org = org_result.first()
                limit = get_saas_settings().default_max_executions_per_day

                if org and org.plan_id:
                    plan_result = await db.exec(select(Plan).where(Plan.id == org.plan_id))
                    plan = plan_result.first()
                    if plan and plan.max_executions_per_day != -1:
                        limit = plan.max_executions_per_day

                # Count today's executions.
                count_result = await db.exec(
                    select(func.sum(UsageRecord.value)).where(
                        UsageRecord.org_id == org_id,
                        UsageRecord.metric == UsageMetric.FLOW_EXECUTION,
                        UsageRecord.recorded_at >= today_start,
                    )
                )
                used = int(count_result.first() or 0)

            if limit == -1:
                return True, -1, used
            return used < limit, limit, used
        except Exception:  # noqa: BLE001
            return True, -1, 0  # Fail open on DB errors.

    async def _record_execution(self, ctx: OrgContextData) -> None:
        try:
            from langflow.services.deps import session_scope

            from langflow_saas.models import UsageRecord

            record = UsageRecord(
                org_id=ctx.org_id,
                user_id=ctx.user_id,
                metric=UsageMetric.FLOW_EXECUTION,
                value=1,
            )
            async with session_scope() as db:
                db.add(record)
                await db.commit()
        except Exception:  # noqa: BLE001
            logger.warning("Failed to record execution usage for org %s", ctx.org_id)
