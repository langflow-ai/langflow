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
``400``, and not ``429``: an anonymous endpoint that distinguishes "no such
trigger" from "bad signature" from "stale timestamp" - or that reveals, by the
request count at which its answer changes, which of two rate-limit buckets a
caller landed in - is an oracle for which trigger ids exist and for how close an
attacker is getting. The reason is recorded in the audit row, where an operator
can read it and an attacker cannot.

The single exception is the Microsoft Graph subscription handshake, and it is an
exception only because it is answered *before* any trigger is resolved: it
echoes the caller's own ``validationToken`` and its response therefore does not
depend on whether the public id exists.

Slack has its own route, ``/slack/apps/{registration_id}``, because a Slack app
has exactly one Request URL for every workspace it is installed in: a delivery
names an app and a workspace, never a trigger, and fans out to every trigger it
matches. Its ``url_verification`` arrives signed, so it is answered on the
verified path - and, since it names no trigger, before a single trigger exists.
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
from langflow.services.triggers.constants import INGRESS_PROVIDERS, PROVIDER_SLACK
from langflow.services.triggers.ingress import intake
from langflow.services.triggers.ingress.verifiers import (
    REASON_BODY_TOO_LARGE,
    REASON_HANDSHAKE,
    REASON_RATE_LIMITED,
    REASON_TRIGGER_NOT_ACCEPTING,
    REASON_UNKNOWN_PROVIDER,
    REASON_UNKNOWN_TRIGGER,
    IngressRejected,
    IngressRequest,
    IngressSecrets,
    validation_token,
    verify,
)
from langflow.services.triggers.providers.slack import ingress as slack_ingress
from langflow.services.triggers.providers.slack.events import SlackControl, normalize

router = APIRouter(prefix="/triggers/ingress", tags=["Triggers"])

#: Counter namespaces, kept apart so a busy Slack workspace cannot exhaust the
#: budget that bounds id probing, and so probing cannot exhaust the budget Graph
#: needs to create and renew subscriptions.
_SCOPE_INGRESS = "trigger_ingress"
_SCOPE_INGRESS_UNKNOWN = "trigger_ingress_unknown"
_SCOPE_INGRESS_HANDSHAKE = "trigger_ingress_handshake"
_SCOPE_SLACK_APP = "trigger_ingress_slack_app"
_SCOPE_SLACK_TEAM = "trigger_ingress_slack_team"

#: The one answer every rejection gets.
_NOT_FOUND = {"detail": "Not found"}

#: Provider ids are a closed set and public ids are opaque; both are constrained
#: in the path so a malformed request never reaches a database query.
_PUBLIC_ID = Annotated[str, Path(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
_PROVIDER = Annotated[str, Path(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")]
#: An OAuth registration id, as the operator named it in
#: ``LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS``. Not a secret - the signing
#: secret is what authenticates a delivery - but still bounded, so a malformed
#: path never reaches the registration lookup.
_REGISTRATION_ID = Annotated[str, Path(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]


def _reject() -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=_NOT_FOUND)


def _unknown_budget_spent(request: Request, limit_per_minute: int) -> bool:
    """Charge this client's probing budget. True when it is exhausted."""
    try:
        check_rate_limit(request, scope=_SCOPE_INGRESS_UNKNOWN, limit_per_minute=limit_per_minute)
    except RateLimitExceeded:
        return True
    return False


def _within_budget(request: Request, *, scope: str, limit_per_minute: int, key: str) -> bool:
    try:
        check_rate_limit(request, scope=scope, limit_per_minute=limit_per_minute, key=key)
    except RateLimitExceeded:
        return False
    return True


async def _bounded_body(request: Request, limit: int) -> bytes | None:
    """Read at most ``limit`` bytes. None means the delivery was too large.

    The declared ``Content-Length`` is checked first so an oversized delivery is
    refused before a single byte is read. A chunked request declares no length,
    and that is the case this function exists for: ``request.body()`` would
    drain the whole stream into memory before anyone could measure it, so an
    anonymous caller could hold hundreds of megabytes per in-flight request -
    the global ``ContentSizeLimitMiddleware`` ceiling is
    ``max_file_size_upload`` (1024 MB by default), not this route's 1 MiB. The
    stream is therefore read incrementally and abandoned the moment the
    accumulated length would exceed the cap.
    """
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > limit:
                return None
        except ValueError:
            return None
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > limit:
            return None
        chunks.extend(chunk)
    return bytes(chunks)


@router.post("/{provider}/{public_id}")
async def receive_provider_delivery(
    request: Request,
    session: DbSession,
    provider: _PROVIDER,
    public_id: _PUBLIC_ID,
) -> Response:
    """Accept one provider delivery and append it to the trigger's ledger."""
    settings = get_settings_service().settings
    unknown_limit = settings.trigger_ingress_unknown_rate_limit_per_minute

    if not settings.trigger_ingress_enabled or provider not in INGRESS_PROVIDERS:
        # Charged before the audit row is written: the audit queue is bounded
        # and single-writer, so a flood of garbage-provider requests would
        # otherwise starve the pipeline that carries legitimate audit signal.
        # No real provider is affected - the provider set is closed, so an
        # unrecognised one is always garbage.
        if _unknown_budget_spent(request, unknown_limit):
            return _reject()
        await intake.audit_ingress(
            accepted=False, provider=provider, public_id=public_id, target=None, reason=REASON_UNKNOWN_PROVIDER
        )
        return _reject()

    # The Microsoft Graph subscription handshake, answered before the trigger is
    # even looked up. Graph POSTs a validationToken when a subscription is
    # created or renewed and expects it echoed verbatim; nothing is verified,
    # because nothing has been subscribed yet - the exchange proves the URL is
    # ours, not that the caller is Graph. Answering it before resolution is what
    # keeps it from being the one path on this route whose response depends on
    # whether a public id exists.
    handshake = validation_token(provider, request.query_params)
    if handshake is not None:
        # Its own counter, at the per-trigger ceiling. Sharing the unknown-id
        # budget let anonymous probing - one key for every caller behind a
        # proxy - deny Graph's subscription creation and renewal instance-wide.
        # The echo reveals nothing, so the budget only bounds cost and audit volume.
        try:
            check_rate_limit(
                request,
                scope=_SCOPE_INGRESS_HANDSHAKE,
                limit_per_minute=settings.trigger_ingress_rate_limit_per_minute,
            )
        except RateLimitExceeded:
            return _reject()
        await intake.audit_ingress(
            accepted=True, provider=provider, public_id=public_id, target=None, reason=REASON_HANDSHAKE
        )
        return PlainTextResponse(content=handshake, media_type="text/plain")

    target = await intake.resolve_target(session, provider=provider, public_id=public_id)

    # Rate-limit before verification, and on the counter that matches what we
    # found: verification is cheap but not free, and an unknown id must not be
    # able to spend a real trigger's budget.
    if target is None:
        limited = _unknown_budget_spent(request, unknown_limit)
    else:
        try:
            check_rate_limit(
                request,
                scope=_SCOPE_INGRESS,
                limit_per_minute=settings.trigger_ingress_rate_limit_per_minute,
                key=f"trigger:{target.trigger_id}",
            )
            limited = False
        except RateLimitExceeded:
            limited = True
    if limited:
        # 404, not 429. The two budgets have different ceilings, so a distinct
        # status would tell a caller which bucket it landed in - that is, which
        # public ids resolve - by the count at which the answer changes. The
        # refusal is recorded in the audit row instead, where an operator can
        # read it. A throttled provider retries, which is the behaviour a 429
        # would have produced anyway.
        await intake.audit_ingress(
            accepted=False, provider=provider, public_id=public_id, target=target, reason=REASON_RATE_LIMITED
        )
        return _reject()

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
            # Scoped to the trigger whose clientState verified this delivery;
            # the subscription id in the body is the caller's claim, not proof.
            await subscriptions.apply_lifecycle(
                session, trigger_id=target.trigger_id, subscription_id=subscription_id, event=event
            )
        await session.commit()
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
    # Commit before auditing. A durable audit waits for the writer's own
    # connection to commit, and on SQLite that cannot happen past this
    # request's open write - the delivery would hang, answer 500, and roll the
    # ledger row back.
    await session.commit()
    await intake.audit_ingress(
        accepted=True, provider=provider, public_id=public_id, target=target, duplicate=not created
    )
    if not created:
        await logger.adebug("Trigger %s: ingress redelivery collapsed by the ledger", target.trigger_id)
    # 2xx for a duplicate too. Answering an error would teach the provider that
    # its retry failed, and it would keep retrying.
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/slack/apps/{registration_id}")
async def receive_slack_app_delivery(
    request: Request,
    session: DbSession,
    registration_id: _REGISTRATION_ID,
) -> Response:
    """Accept one Slack Events API delivery and fan it out to the triggers it fires.

    The same pipeline as the per-trigger route, with the app in place of the
    trigger: resolve the registration, rate-limit, read a bounded body, verify
    Slack's signature with the registration's signing secret, and only then
    touch the database. Every refusal is the same ``404``.
    """
    settings = get_settings_service().settings
    app = slack_ingress.resolve_app(registration_id) if settings.trigger_ingress_enabled else None
    if app is None:
        if _unknown_budget_spent(request, settings.trigger_ingress_unknown_rate_limit_per_minute):
            return _reject()
        await slack_ingress.audit_delivery(
            accepted=False, registration_id=registration_id, reason=slack_ingress.REASON_UNKNOWN_APP
        )
        return _reject()

    if not _within_budget(
        request,
        scope=_SCOPE_SLACK_APP,
        limit_per_minute=settings.trigger_ingress_slack_app_rate_limit_per_minute,
        key=f"slack-app:{registration_id}",
    ):
        await slack_ingress.audit_delivery(accepted=False, registration_id=registration_id, reason=REASON_RATE_LIMITED)
        return _reject()

    body = await _bounded_body(request, settings.trigger_ingress_max_body_bytes)
    if body is None:
        await slack_ingress.audit_delivery(
            accepted=False, registration_id=registration_id, reason=REASON_BODY_TOO_LARGE
        )
        return _reject()

    try:
        verified = verify(
            IngressRequest(provider=PROVIDER_SLACK, body=body, headers=request.headers, query=request.query_params),
            IngressSecrets(signing_secret=app.signing_secret),
            tolerance_s=settings.trigger_ingress_signature_tolerance_s,
        )
    except IngressRejected as rejection:
        await slack_ingress.audit_delivery(accepted=False, registration_id=registration_id, reason=rejection.reason)
        return _reject()

    retry = {
        "retry_num": request.headers.get("X-Slack-Retry-Num"),
        "retry_reason": request.headers.get("X-Slack-Retry-Reason"),
    }
    if verified.handshake is not None:
        # The Request URL handshake. It names no trigger, so it succeeds for an
        # app with none armed yet - which is exactly when an operator saves the
        # URL in the Slack app configuration.
        await slack_ingress.audit_delivery(accepted=True, registration_id=registration_id, reason=REASON_HANDSHAKE)
        return PlainTextResponse(content=verified.handshake, media_type=verified.handshake_media_type)

    event = normalize(verified.payload)
    if isinstance(event, SlackControl):
        # ``app_rate_limited``: Slack stopped delivering this workspace's events
        # for the rest of the minute. Nothing to run; the audit row is how an
        # operator learns why a workspace went quiet.
        await slack_ingress.audit_delivery(
            accepted=True,
            registration_id=registration_id,
            reason=slack_ingress.REASON_APP_RATE_LIMITED,
            team_id=event.team_id,
            **retry,
        )
        return Response(status_code=status.HTTP_200_OK)
    if event is None:
        # A type no trigger subscribes to. Acknowledged, so Slack does not retry it.
        await slack_ingress.audit_delivery(
            accepted=True, registration_id=registration_id, reason=slack_ingress.REASON_IGNORED, **retry
        )
        return Response(status_code=status.HTTP_200_OK)

    # Per workspace, after verification: the workspace is only known from the
    # signed body, and only a leaked signing secret can reach this ceiling.
    if not _within_budget(
        request,
        scope=_SCOPE_SLACK_TEAM,
        limit_per_minute=settings.trigger_ingress_slack_team_rate_limit_per_minute,
        key=f"slack-team:{registration_id}:{event.payload['team_id']}",
    ):
        await slack_ingress.audit_delivery(
            accepted=False, registration_id=registration_id, reason=REASON_RATE_LIMITED, event=event, **retry
        )
        return _reject()

    fanout = await slack_ingress.fan_out(session, registration_id=registration_id, event=event)
    # One commit for the whole delivery, and the acknowledgement only after it:
    # a slow commit answers Slack late and Slack retries, which the ledger's
    # (trigger, event_id) key collapses. Answering before the commit is the
    # only order that could lose an event, so it is the one this never does.
    await session.commit()
    await slack_ingress.audit_delivery(
        accepted=True, registration_id=registration_id, event=event, fanout=fanout, **retry
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)
