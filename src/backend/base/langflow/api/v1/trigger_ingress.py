"""The unauthenticated provider ingress route.

This is the only route in Langflow that accepts a write from a caller with no
session, no API key, and no user - so the whole file is written to be read by
somebody deciding whether to expose it. What happens, in order:

1. Read a bounded body. The global request limit is far too large to be the
   only protection on an anonymous endpoint, and provider notifications are
   small.
2. Rate-limit. Known triggers get a generous per-trigger budget; anything that
   names no known trigger gets a much smaller per-client one, so probing for
   valid ids is bounded without a real provider's retries sharing that budget.
3. Verify with the provider's own scheme (``services/triggers/ingress``).
4. Deduplicate and commit one ledger row.
5. Answer inside the provider's deadline.

What deliberately does **not** happen: no flow runs, and nothing is fetched back
from the provider. A Graph basic notification carries ids only, and resolving it
needs the owner's connection and an outbound call - which is both an SSRF-class
surface in an unauthenticated request and a guaranteed way to miss Slack's
three-second acknowledgement window. The dispatcher runs the flow afterwards,
as the trigger owner, and the run does the fetching.

Every failure answers ``404`` with the same body. Not ``401``, not ``403``, not
``400``: an anonymous endpoint that distinguishes "no such trigger" from "bad
signature" from "stale timestamp" is an oracle for which trigger ids exist and
for how close an attacker is getting. The reason is recorded in the audit row,
where an operator can read it and an attacker cannot.
"""

from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Path, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from lfx.log.logger import logger
from slowapi.errors import RateLimitExceeded

from langflow.api.utils import DbSession
from langflow.services.deps import get_settings_service
from langflow.services.rate_limit.service import check_rate_limit
from langflow.services.triggers.constants import INGRESS_PROVIDERS
from langflow.services.triggers.ingress import intake
from langflow.services.triggers.ingress.verifiers import (
    REASON_BODY_TOO_LARGE,
    REASON_RATE_LIMITED,
    REASON_TRIGGER_NOT_ACCEPTING,
    REASON_UNKNOWN_PROVIDER,
    REASON_UNKNOWN_TRIGGER,
    IngressRejected,
    IngressRequest,
    verify,
)

router = APIRouter(prefix="/triggers/ingress", tags=["Triggers"])

#: Counter namespaces, kept apart so a busy Slack workspace cannot exhaust the
#: budget that bounds id probing.
_SCOPE_INGRESS = "trigger_ingress"
_SCOPE_INGRESS_UNKNOWN = "trigger_ingress_unknown"

#: The one answer every rejection gets.
_NOT_FOUND = {"detail": "Not found"}

#: Provider ids are a closed set and public ids are opaque; both are constrained
#: in the path so a malformed request never reaches a database query.
_PUBLIC_ID = Annotated[str, Path(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
_PROVIDER = Annotated[str, Path(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")]


def _reject() -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=_NOT_FOUND)


async def _bounded_body(request: Request, limit: int) -> bytes | None:
    """Read at most ``limit`` bytes. None means the delivery was too large.

    The declared ``Content-Length`` is checked first so an oversized delivery is
    refused without being read, and the body is measured afterwards anyway
    because a chunked request declares no length at all.
    """
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > limit:
                return None
        except ValueError:
            return None
    body = await request.body()
    return None if len(body) > limit else body


@router.post("/{provider}/{public_id}")
async def receive_provider_delivery(
    request: Request,
    session: DbSession,
    provider: _PROVIDER,
    public_id: _PUBLIC_ID,
) -> Response:
    """Accept one provider delivery and append it to the trigger's ledger."""
    settings = get_settings_service().settings
    if not settings.trigger_ingress_enabled or provider not in INGRESS_PROVIDERS:
        await intake.audit_ingress(
            accepted=False, provider=provider, public_id=public_id, target=None, reason=REASON_UNKNOWN_PROVIDER
        )
        return _reject()

    target = await intake.resolve_target(session, provider=provider, public_id=public_id)

    # Rate-limit before verification, and on the counter that matches what we
    # found: verification is cheap but not free, and an unknown id must not be
    # able to spend a real trigger's budget.
    try:
        if target is None:
            check_rate_limit(
                request,
                scope=_SCOPE_INGRESS_UNKNOWN,
                limit_per_minute=settings.trigger_ingress_unknown_rate_limit_per_minute,
            )
        else:
            check_rate_limit(
                request,
                scope=_SCOPE_INGRESS,
                limit_per_minute=settings.trigger_ingress_rate_limit_per_minute,
                key=f"trigger:{target.trigger_id}",
            )
    except RateLimitExceeded:
        await intake.audit_ingress(
            accepted=False, provider=provider, public_id=public_id, target=target, reason=REASON_RATE_LIMITED
        )
        return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": "Too many requests"})

    body = await _bounded_body(request, settings.trigger_ingress_max_body_bytes)
    if body is None:
        await intake.audit_ingress(
            accepted=False, provider=provider, public_id=public_id, target=target, reason=REASON_BODY_TOO_LARGE
        )
        return _reject()

    if target is None:
        await intake.audit_ingress(
            accepted=False, provider=provider, public_id=public_id, target=None, reason=REASON_UNKNOWN_TRIGGER
        )
        return _reject()
    if not target.accepting:
        # Paused, expired, dead, or waiting on a reconnect. The provider may
        # still be pushing; the delivery is dropped rather than queued to run at
        # a surprising moment after the owner re-enables the trigger.
        await intake.audit_ingress(
            accepted=False,
            provider=provider,
            public_id=public_id,
            target=target,
            reason=REASON_TRIGGER_NOT_ACCEPTING,
        )
        return _reject()

    try:
        verified = verify(
            IngressRequest(
                provider=provider,
                body=body,
                headers=request.headers,
                query=request.query_params,
            ),
            target.secrets,
            tolerance_s=settings.trigger_ingress_signature_tolerance_s,
        )
    except IngressRejected as rejection:
        await intake.audit_ingress(
            accepted=False, provider=provider, public_id=public_id, target=target, reason=rejection.reason
        )
        return _reject()

    if verified.lifecycle:
        # Graph is telling us the subscription needs attention, not that
        # something happened in the mailbox. Acting on it is what keeps a
        # stopped trigger from looking healthy.
        from langflow.services.triggers import subscriptions

        for subscription_id, event in verified.lifecycle:
            await subscriptions.apply_lifecycle(session, subscription_id=subscription_id, event=event)
        await intake.audit_ingress(accepted=True, provider=provider, public_id=public_id, target=target)
        return Response(status_code=status.HTTP_202_ACCEPTED)

    if verified.handshake is not None:
        # A subscription-lifecycle exchange, not an event: Graph's
        # ``validationToken`` echo or Slack's ``url_verification`` challenge.
        # Writing it to the ledger would fire the flow with a payload that means
        # nothing to it.
        await intake.audit_ingress(accepted=True, provider=provider, public_id=public_id, target=target)
        return PlainTextResponse(content=verified.handshake, media_type=verified.handshake_media_type)

    fallback = hashlib.sha256(body).hexdigest()[:32]
    _row, created = await intake.record_event(
        session,
        target=target,
        provider=provider,
        payload=verified.payload,
        suffix=verified.dedupe_suffix,
        fallback=fallback,
    )
    await intake.audit_ingress(
        accepted=True, provider=provider, public_id=public_id, target=target, duplicate=not created
    )
    if not created:
        await logger.adebug("Trigger %s: ingress redelivery collapsed by the ledger", target.trigger_id)
    # 2xx for a duplicate too. Answering an error would teach the provider that
    # its retry failed, and it would keep retrying.
    return Response(status_code=status.HTTP_202_ACCEPTED)
