"""The unauthenticated ingress route, end to end.

The two things worth proving about an anonymous write endpoint are that a real
delivery becomes exactly one ledger row, and that everything else is
indistinguishable from everything else. Both are here, against the real route,
the real ledger, and the real unique index.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import session_scope
from langflow.services.triggers.ingress.verifiers import sign_webhook_payload
from sqlmodel import select

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

SLACK_SECRET = "slack-signing-secret"  # noqa: S105 - test fixture  # pragma: allowlist secret


async def _arm_trigger(flow_id, owner_id, *, kind: str, public_id: str, state: str = "active", **fields) -> Trigger:
    async with session_scope() as session:
        row = Trigger(
            flow_id=flow_id,
            user_id=owner_id,
            name="ingress",
            kind=kind,
            config={},
            provider_state={},
            state=state,
            public_id=public_id,
            concurrency_limit=1,
            max_attempts=3,
            **fields,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row


async def _events(trigger_id) -> list[TriggerEvent]:
    identifier = trigger_id if isinstance(trigger_id, UUID) else UUID(str(trigger_id))
    async with session_scope() as session:
        return list((await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == identifier))).all())


def _slack_headers(body: bytes, *, secret: str = SLACK_SECRET) -> dict[str, str]:
    timestamp = str(int(time.time()))
    basestring = f"v0:{timestamp}:".encode() + body
    return {
        "X-Slack-Signature": "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest(),
        "X-Slack-Request-Timestamp": timestamp,
        "Content-Type": "application/json",
    }


@pytest.fixture
def slack_registration(monkeypatch):
    """Stand in for the operator-configured Slack app signing secret."""
    from langflow.services.triggers.ingress import intake

    async def _secret(_session, _row) -> str:
        return SLACK_SECRET

    monkeypatch.setattr(intake, "_slack_signing_secret", _secret)


# --------------------------------------------------------------------------- #
# The happy path
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("slack_registration")
async def test_a_valid_slack_delivery_becomes_one_ledger_row(client: AsyncClient, active_user, flow) -> None:
    public_id = uuid4().hex
    trigger = await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)
    body = json.dumps(
        {"type": "event_callback", "event_id": "Ev999", "event": {"type": "message", "text": "hello"}}
    ).encode()

    response = await client.post(
        f"api/v1/triggers/ingress/slack/{public_id}", content=body, headers=_slack_headers(body)
    )

    assert response.status_code == 202, response.text
    rows = await _events(trigger.id)
    assert len(rows) == 1
    assert rows[0].dedupe_key == "ingress:slack:Ev999"
    assert rows[0].payload["delivery"]["event"]["text"] == "hello"
    # The request ran nothing: the dispatcher does that, afterwards.
    assert rows[0].state == "pending"
    assert rows[0].job_id is None


@pytest.mark.usefixtures("slack_registration")
async def test_slack_retries_produce_exactly_one_run(client: AsyncClient, active_user, flow) -> None:
    """Slack retries at 0, 1 and 5 minutes when it misses an acknowledgement."""
    public_id = uuid4().hex
    trigger = await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)
    body = json.dumps({"type": "event_callback", "event_id": "Ev-retry", "event": {"ts": "1"}}).encode()

    statuses = []
    for _ in range(3):
        response = await client.post(
            f"api/v1/triggers/ingress/slack/{public_id}", content=body, headers=_slack_headers(body)
        )
        statuses.append(response.status_code)

    # Every retry is acknowledged: answering an error would teach Slack to retry forever.
    assert statuses == [202, 202, 202]
    assert len(await _events(trigger.id)) == 1


@pytest.mark.usefixtures("slack_registration")
async def test_the_slack_url_verification_challenge_is_echoed(client: AsyncClient, active_user, flow) -> None:
    public_id = uuid4().hex
    trigger = await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)
    body = json.dumps({"type": "url_verification", "challenge": "chal-123"}).encode()

    response = await client.post(
        f"api/v1/triggers/ingress/slack/{public_id}", content=body, headers=_slack_headers(body)
    )

    assert response.status_code == 200
    assert response.text == "chal-123"
    # A handshake is not an event.
    assert await _events(trigger.id) == []


async def test_a_signed_webhook_delivery_becomes_a_ledger_row(
    client: AsyncClient, logged_in_headers: dict[str, str], flow
) -> None:
    created = await client.post(
        "api/v1/triggers",
        json={"flow_id": str(flow.id), "name": "orders", "kind": "inbound_webhook", "config": {}},
        headers=logged_in_headers,
    )
    assert created.status_code == 201, created.text
    trigger_id = created.json()["id"]
    await client.post(f"api/v1/triggers/{trigger_id}/enable", headers=logged_in_headers)

    minted = await client.post(f"api/v1/triggers/{trigger_id}/signing-secret", headers=logged_in_headers)
    assert minted.status_code == 200, minted.text
    secret = minted.json()["signing_secret"]
    url = minted.json()["ingress_url"]
    assert minted.json()["has_signing_secret"] is True

    body = json.dumps({"order": 42}).encode()
    timestamp = int(time.time())
    response = await client.post(
        url,
        content=body,
        headers={
            "X-Langflow-Signature": sign_webhook_payload(secret, timestamp=timestamp, body=body),
            "X-Langflow-Timestamp": str(timestamp),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 202, response.text
    rows = await _events(trigger_id)
    assert len(rows) == 1
    assert rows[0].payload["delivery"] == {"order": 42}


async def test_rotating_the_secret_invalidates_the_old_one_immediately(
    client: AsyncClient, logged_in_headers: dict[str, str], flow
) -> None:
    created = await client.post(
        "api/v1/triggers",
        json={"flow_id": str(flow.id), "name": "orders", "kind": "inbound_webhook", "config": {}},
        headers=logged_in_headers,
    )
    trigger_id = created.json()["id"]
    await client.post(f"api/v1/triggers/{trigger_id}/enable", headers=logged_in_headers)

    first = (await client.post(f"api/v1/triggers/{trigger_id}/signing-secret", headers=logged_in_headers)).json()
    second = (await client.post(f"api/v1/triggers/{trigger_id}/signing-secret", headers=logged_in_headers)).json()

    # The address survives rotation; the secret does not.
    assert first["public_id"] == second["public_id"]
    assert first["signing_secret"] != second["signing_secret"]

    body = b'{"order": 1}'
    timestamp = int(time.time())
    stale = await client.post(
        first["ingress_url"],
        content=body,
        headers={
            "X-Langflow-Signature": sign_webhook_payload(first["signing_secret"], timestamp=timestamp, body=body),
            "X-Langflow-Timestamp": str(timestamp),
        },
    )
    assert stale.status_code == 404
    assert await _events(trigger_id) == []


# --------------------------------------------------------------------------- #
# Existence privacy: every refusal looks the same
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("slack_registration")
async def test_an_unknown_public_id_is_indistinguishable_from_a_bad_signature(
    client: AsyncClient, active_user, flow
) -> None:
    known = uuid4().hex
    await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=known)
    body = json.dumps({"type": "event_callback", "event_id": "Ev1"}).encode()

    unknown = await client.post(
        f"api/v1/triggers/ingress/slack/{uuid4().hex}", content=body, headers=_slack_headers(body)
    )
    forged = await client.post(
        f"api/v1/triggers/ingress/slack/{known}",
        content=body,
        headers=_slack_headers(body, secret="wrong"),  # noqa: S106 - a deliberately wrong secret
    )

    assert unknown.status_code == forged.status_code == 404
    assert unknown.json() == forged.json()


@pytest.mark.usefixtures("slack_registration")
async def test_every_rejection_looks_identical_to_the_caller(client: AsyncClient, active_user, flow) -> None:
    """Unknown id, wrong provider, paused trigger, unsigned body: one answer."""
    public_id = uuid4().hex
    await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)
    paused_id = uuid4().hex
    await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=paused_id, state="paused")
    body = json.dumps({"type": "event_callback", "event_id": "Ev1"}).encode()
    headers = _slack_headers(body)

    answers = [
        await client.post(f"api/v1/triggers/ingress/slack/{uuid4().hex}", content=body, headers=headers),
        # A Slack-signed delivery must not be able to drive a Microsoft trigger.
        await client.post(f"api/v1/triggers/ingress/microsoft/{public_id}", content=body, headers=headers),
        await client.post(f"api/v1/triggers/ingress/slack/{paused_id}", content=body, headers=headers),
        await client.post(f"api/v1/triggers/ingress/slack/{public_id}", content=body),
        await client.post(f"api/v1/triggers/ingress/dropbox/{public_id}", content=body, headers=headers),
    ]

    assert {answer.status_code for answer in answers} == {404}
    assert {answer.text for answer in answers} == {answers[0].text}


@pytest.mark.usefixtures("slack_registration")
async def test_an_oversized_body_is_refused_without_being_stored(client: AsyncClient, active_user, flow) -> None:
    from langflow.services.deps import get_settings_service

    public_id = uuid4().hex
    trigger = await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)
    limit = get_settings_service().settings.trigger_ingress_max_body_bytes
    body = json.dumps({"type": "event_callback", "event_id": "Ev1", "pad": "x" * (limit + 1024)}).encode()

    response = await client.post(
        f"api/v1/triggers/ingress/slack/{public_id}", content=body, headers=_slack_headers(body)
    )

    assert response.status_code == 404
    assert await _events(trigger.id) == []


@pytest.mark.usefixtures("slack_registration")
async def test_a_paused_trigger_drops_deliveries_rather_than_queueing_them(
    client: AsyncClient, active_user, flow
) -> None:
    """A provider may keep pushing; those runs must not happen on re-enable."""
    public_id = uuid4().hex
    trigger = await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id, state="paused")
    body = json.dumps({"type": "event_callback", "event_id": "Ev1"}).encode()

    response = await client.post(
        f"api/v1/triggers/ingress/slack/{public_id}", content=body, headers=_slack_headers(body)
    )

    assert response.status_code == 404
    assert await _events(trigger.id) == []


# --------------------------------------------------------------------------- #
# Owner-facing management of the webhook address
# --------------------------------------------------------------------------- #


async def test_only_the_flow_owner_can_mint_a_signing_secret(
    client: AsyncClient, logged_in_headers: dict[str, str], flow
) -> None:
    """The management routes authorize on the flow, however public the ingress route beside them is."""
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User

    owned = await client.post(
        "api/v1/triggers",
        json={"flow_id": str(flow.id), "name": "orders", "kind": "inbound_webhook", "config": {}},
        headers=logged_in_headers,
    )
    assert owned.status_code == 201, owned.text
    minted = await client.post(f"api/v1/triggers/{owned.json()['id']}/signing-secret", headers=logged_in_headers)
    assert minted.status_code == 200, minted.text

    async with session_scope() as session:
        stranger = User(
            username=f"stranger-{uuid4().hex[:8]}",
            password="hashed-not-used",  # noqa: S106  # pragma: allowlist secret
            is_active=True,
            is_superuser=False,
        )
        session.add(stranger)
        await session.flush()
        stranger_flow = Flow(name=f"stranger-flow-{uuid4().hex[:6]}", user_id=stranger.id)
        session.add(stranger_flow)
        await session.flush()
        stranger_trigger = Trigger(
            flow_id=stranger_flow.id,
            user_id=stranger.id,
            name="not yours",
            kind="inbound_webhook",
            config={},
            provider_state={},
            concurrency_limit=1,
            max_attempts=5,
        )
        session.add(stranger_trigger)
        await session.flush()
        stranger_trigger_id = stranger_trigger.id

    # 404, not 403: a trigger whose flow the caller cannot read must not be an
    # existence oracle, and minting a secret for it is certainly not allowed.
    foreign = await client.post(f"api/v1/triggers/{stranger_trigger_id}/signing-secret", headers=logged_in_headers)
    assert foreign.status_code == 404, foreign.text
    async with session_scope() as session:
        refreshed = await session.get(Trigger, stranger_trigger_id)
        assert refreshed.public_id is None
        assert refreshed.signing_secret_encrypted is None


async def test_the_secret_is_shown_once_and_never_read_back(
    client: AsyncClient, logged_in_headers: dict[str, str], flow
) -> None:
    created = await client.post(
        "api/v1/triggers",
        json={"flow_id": str(flow.id), "name": "orders", "kind": "inbound_webhook", "config": {}},
        headers=logged_in_headers,
    )
    trigger_id = created.json()["id"]
    minted = (await client.post(f"api/v1/triggers/{trigger_id}/signing-secret", headers=logged_in_headers)).json()

    read_back = await client.get(f"api/v1/triggers/{trigger_id}/ingress", headers=logged_in_headers)

    assert read_back.status_code == 200, read_back.text
    assert "signing_secret" not in read_back.json()
    assert read_back.json()["has_signing_secret"] is True
    assert read_back.json()["public_id"] == minted["public_id"]


async def test_a_schedule_trigger_has_no_owner_managed_secret(
    client: AsyncClient, logged_in_headers: dict[str, str], flow
) -> None:
    """Slack and Graph verify against secrets the owner does not control."""
    created = await client.post(
        "api/v1/triggers",
        json={
            "flow_id": str(flow.id),
            "name": "digest",
            "kind": "schedule",
            "config": {"cron": "0 8 * * 1-5", "timezone": "UTC"},
        },
        headers=logged_in_headers,
    )
    trigger_id = created.json()["id"]

    response = await client.post(f"api/v1/triggers/{trigger_id}/signing-secret", headers=logged_in_headers)

    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# The acknowledgement budget
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("slack_registration")
async def test_a_hundred_concurrent_deliveries_are_acknowledged_without_calling_out(
    client: AsyncClient, active_user, flow, monkeypatch
) -> None:
    """Slack gives three seconds, then retries at zero, one, and five minutes.

    The budget is spent on verification and one ledger insert, and on nothing
    else. Outbound HTTP is made to explode for the duration so that a fetch-back
    added later - resolving a thin notification, say - fails this test instead
    of quietly turning every delivery into a retry storm in production.
    """
    import asyncio

    import httpx

    async def _no_outbound(*_args, **_kwargs):
        msg = "ingress must not make outbound HTTP calls inside the request"
        raise AssertionError(msg)

    # The real-network transport only. The test client itself speaks ASGI, so
    # blocking this blocks exactly what the route must not do and nothing else.
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _no_outbound)

    public_id = uuid4().hex
    trigger = await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)
    deliveries = [
        json.dumps({"type": "event_callback", "event_id": f"Ev-{index}", "event": {"ts": str(index)}}).encode()
        for index in range(100)
    ]

    responses = await asyncio.gather(
        *[
            client.post(f"api/v1/triggers/ingress/slack/{public_id}", content=body, headers=_slack_headers(body))
            for body in deliveries
        ]
    )

    assert {response.status_code for response in responses} == {202}
    assert len(await _events(trigger.id)) == 100


# --------------------------------------------------------------------------- #
# Review follow-ups: bounded reads, uniform refusals, no handshake oracle
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("slack_registration")
async def test_a_chunked_oversized_body_is_refused_without_being_buffered(
    client: AsyncClient, active_user, flow
) -> None:
    """A chunked request declares no Content-Length.

    `request.body()` would drain the whole stream into memory first, so an
    anonymous caller could hold hundreds of megabytes per in-flight request.
    The route reads incrementally and abandons the stream at the cap; this test
    sends more than the cap with no declared length and asserts nothing lands.
    """
    from langflow.services.deps import get_settings_service

    public_id = uuid4().hex
    trigger = await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)
    limit = get_settings_service().settings.trigger_ingress_max_body_bytes
    chunk = b"x" * 65536
    sent = 0

    async def _oversized():
        nonlocal sent
        while sent <= limit:
            sent += len(chunk)
            yield chunk

    response = await client.post(
        f"api/v1/triggers/ingress/slack/{public_id}",
        content=_oversized(),
        headers={"Content-Type": "application/json", "Transfer-Encoding": "chunked"},
    )

    assert response.status_code == 404
    assert await _events(trigger.id) == []


@pytest.mark.usefixtures("slack_registration")
async def test_a_rate_limited_delivery_answers_like_every_other_refusal(
    client: AsyncClient, active_user, flow, monkeypatch
) -> None:
    """429 would leak which bucket a caller landed in — that is, which ids resolve.

    The two budgets have different ceilings, so a distinct status code tells a
    prober whether a public id exists by the count at which the answer changes.
    """
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "trigger_ingress_rate_limit_per_minute", 1)
    monkeypatch.setattr(settings, "trigger_ingress_unknown_rate_limit_per_minute", 1)

    public_id = uuid4().hex
    await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)
    body = json.dumps({"type": "event_callback", "event_id": "Ev-limit"}).encode()

    known = [
        await client.post(f"api/v1/triggers/ingress/slack/{public_id}", content=body, headers=_slack_headers(body))
        for _ in range(3)
    ]
    unknown = await client.post(
        f"api/v1/triggers/ingress/slack/{uuid4().hex}", content=body, headers=_slack_headers(body)
    )

    assert {response.status_code for response in known} == {202, 404}
    assert known[-1].status_code == 404
    assert known[-1].text == unknown.text


async def test_the_graph_handshake_does_not_reveal_whether_a_trigger_exists(
    client: AsyncClient, active_user, flow
) -> None:
    """The one exchange with no provider proof must not depend on the id resolving."""
    public_id = uuid4().hex
    await _arm_trigger(flow.id, active_user.id, kind="microsoft.mail", public_id=public_id)

    known = await client.post(f"api/v1/triggers/ingress/microsoft/{public_id}?validationToken=tok-1", content=b"")
    unknown = await client.post(f"api/v1/triggers/ingress/microsoft/{uuid4().hex}?validationToken=tok-1", content=b"")

    assert known.status_code == unknown.status_code == 200
    assert known.text == unknown.text == "tok-1"
    assert known.headers["content-type"].startswith("text/plain")


async def test_a_slack_request_carrying_a_validation_token_is_still_verified(
    client: AsyncClient, active_user, flow
) -> None:
    """The handshake short-circuit is Microsoft's alone; it is not a bypass."""
    public_id = uuid4().hex
    trigger = await _arm_trigger(flow.id, active_user.id, kind="slack.message", public_id=public_id)

    response = await client.post(
        f"api/v1/triggers/ingress/slack/{public_id}?validationToken=tok-1", content=b'{"type":"event_callback"}'
    )

    assert response.status_code == 404
    assert await _events(trigger.id) == []


async def test_an_unknown_provider_is_rate_limited_before_it_is_audited(client: AsyncClient, monkeypatch) -> None:
    """The audit queue is bounded: garbage must not starve legitimate signal."""
    from langflow.services.triggers.ingress import intake

    audited: list[str] = []

    async def _record(*, accepted, provider, public_id, target=None, reason=None, duplicate=False):  # noqa: ARG001
        audited.append(reason or "")

    monkeypatch.setattr(intake, "audit_ingress", _record)
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_unknown_rate_limit_per_minute", 2)

    responses = [await client.post(f"api/v1/triggers/ingress/dropbox/{uuid4().hex}", content=b"{}") for _ in range(5)]

    assert {response.status_code for response in responses} == {404}
    # The budget stopped the audit rows well before the request flood did.
    assert len(audited) <= 2


# --------------------------------------------------------------------------- #
# QA regressions
# --------------------------------------------------------------------------- #


async def _armed_webhook(client: AsyncClient, headers: dict[str, str], flow) -> tuple[str, dict]:
    """An enabled inbound webhook with a minted address and secret, via the API."""
    created = await client.post(
        "api/v1/triggers",
        json={"flow_id": str(flow.id), "name": "orders", "kind": "inbound_webhook", "config": {}},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    trigger_id = created.json()["id"]
    await client.post(f"api/v1/triggers/{trigger_id}/enable", headers=headers)
    minted = await client.post(f"api/v1/triggers/{trigger_id}/signing-secret", headers=headers)
    assert minted.status_code == 200, minted.text
    return trigger_id, minted.json()


@pytest.mark.parametrize(
    ("signature", "timestamp", "reason"),
    [
        ("v1=anything", "inf", "stale_timestamp"),
        ("v1=anything", "1e400", "stale_timestamp"),
        (b"v1=\xff", None, "bad_signature"),
    ],
    ids=["inf", "overflowing-exponent", "non-ascii-signature"],
)
async def test_a_malformed_header_on_a_real_trigger_is_an_audited_404(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    flow,
    monkeypatch,
    signature: str | bytes,
    timestamp: str | None,
    reason: str,
) -> None:
    """A 500 that only a resolving id can produce is the oracle the uniform 404 closes.

    ``int(float("inf"))`` raises OverflowError and ``hmac.compare_digest``
    raises TypeError for a non-ASCII str; neither is a refusal, so both used to
    escape as 500 - and write no audit row.
    """
    from langflow.services.authorization.audit import drain_pending_audit_writes
    from langflow.services.database.models.auth import AuthzAuditLog
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_AUDIT_ENABLED", True)
    trigger_id, minted = await _armed_webhook(client, logged_in_headers, flow)
    headers = {
        "X-Langflow-Signature": signature,
        "X-Langflow-Timestamp": timestamp or str(int(time.time())),
    }
    try:
        real = await client.post(minted["ingress_url"], content=b"{}", headers=headers)
        unknown = await client.post(f"api/v1/triggers/ingress/webhook/{uuid4().hex}", content=b"{}", headers=headers)
        await drain_pending_audit_writes()
    finally:
        await drain_pending_audit_writes()

    assert real.status_code == unknown.status_code == 404
    assert real.text == unknown.text
    async with session_scope() as session:
        audits = (
            await session.exec(
                select(AuthzAuditLog).where(
                    AuthzAuditLog.action == "trigger_ingress:reject",
                    AuthzAuditLog.resource_id == UUID(trigger_id),
                )
            )
        ).all()
    assert [audit.details["reason"] for audit in audits] == [reason]


async def test_an_accepted_delivery_commits_before_the_durable_audit_waits(
    client: AsyncClient, logged_in_headers: dict[str, str], flow, monkeypatch
) -> None:
    """On SQLite the durable audit writer cannot commit past an open write transaction.

    Auditing with the ledger row still uncommitted hung the request until the
    writer gave up, answered 500, and rolled the row back - the delivery was
    lost and the flow never ran.
    """
    import asyncio

    from langflow.services.authorization.audit import drain_pending_audit_writes
    from langflow.services.deps import get_settings_service

    trigger_id, minted = await _armed_webhook(client, logged_in_headers, flow)
    auth_settings = get_settings_service().auth_settings
    monkeypatch.setattr(auth_settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(auth_settings, "AUTHZ_AUDIT_DURABLE", True)
    body = json.dumps({"order": 7}).encode()
    timestamp = int(time.time())
    try:
        response = await asyncio.wait_for(
            client.post(
                minted["ingress_url"],
                content=body,
                headers={
                    "X-Langflow-Signature": sign_webhook_payload(
                        minted["signing_secret"], timestamp=timestamp, body=body
                    ),
                    "X-Langflow-Timestamp": str(timestamp),
                },
            ),
            timeout=10,
        )
    finally:
        await drain_pending_audit_writes()

    assert response.status_code == 202, response.text
    assert len(await _events(trigger_id)) == 1


async def test_probing_cannot_spend_the_graph_handshake_budget(client: AsyncClient, monkeypatch) -> None:
    """Graph creates and renews subscriptions through the handshake.

    Charged to the unknown-id counter, sixty anonymous probes a minute - one
    shared key for every caller behind a proxy - would make subscription
    creation and renewal fail instance-wide.
    """
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_unknown_rate_limit_per_minute", 1)

    probes = [await client.post(f"api/v1/triggers/ingress/webhook/{uuid4().hex}", content=b"{}") for _ in range(3)]
    handshake = await client.post(
        f"api/v1/triggers/ingress/microsoft/{uuid4().hex}?validationToken=tok-after-probing", content=b""
    )

    assert {probe.status_code for probe in probes} == {404}
    assert handshake.status_code == 200
    assert handshake.text == "tok-after-probing"
